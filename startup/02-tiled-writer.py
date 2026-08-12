import math
import copy
import numpy
import os
import warnings
from typing import Literal

import numpy as np

from bluesky_tiled_plugins import TiledWriter
from bluesky_tiled_plugins.writing.consolidators import list_summands
from bluesky.callbacks.buffer import BufferingWrapper
from tiled.client import from_uri
from tiled.mimetypes import DEFAULT_ADAPTERS_BY_MIMETYPE
from tiled.structures.array import StructDtype
from tiled.structures.data_source import Asset

# Define document-specific patches to be applied before sending them to TiledWriter
pb1_columns = ("ts_s", "ts_ns", "encoder", "index", "state")
pb1_dtype_list = [(name, "<i8") for name in pb1_columns]
pb1_dtype = numpy.dtype(pb1_dtype_list)

apb_columns = ("timestamp", "i0", "it", "ir", "iff", "aux1", "aux2", "aux3", "aux4")
apb_dtype_list = [("timestamp", "<f8")] + [(name, "<i4") for name in apb_columns[1:]]
apb_dtype = numpy.dtype(apb_dtype_list)

apb_trigger_dtype = numpy.dtype([("timestamp", "<f8"), ("transition", "<i4")])
LENGTH = 100_000


def patch_descriptor(doc):
    doc = copy.deepcopy(doc)

    if "pb1_enc1" in doc["data_keys"]:
        data_key = doc["data_keys"]["pb1_enc1"]
        data_key["dtype_str"] = pb1_dtype.str
        data_key["dtype_descr"] = pb1_dtype.descr
        data_key["shape"] = (LENGTH,)
    if "apb_stream" in doc["data_keys"]:
        data_key = doc["data_keys"]["apb_stream"]
        data_key["dtype_str"] = apb_dtype.str
        data_key["dtype_descr"] = apb_dtype.descr
        data_key["shape"] = (LENGTH,)
    if "apb_trigger" in doc["data_keys"]:
        data_key = doc["data_keys"]["apb_trigger"]
        data_key["dtype_str"] = apb_trigger_dtype.str
        data_key["dtype_descr"] = apb_trigger_dtype.descr
        data_key["shape"] = (LENGTH,)
    if "xs_stream" in doc["data_keys"]:
        data_key = doc["data_keys"]["xs_stream"]
        data_key["dtype_str"] = "<f8"
        data_key["shape"] = tuple([1, *data_key.get("shape", (1, 6, 4096))[1:]])
    if "pilatus_image" in doc["data_keys"]:
        data_key = doc["data_keys"]["pilatus_image"]
        data_key["dtype_str"] = "<u2"
    if "pe1_image" in doc["data_keys"]:
        data_key = doc["data_keys"]["pe1_image"]
        data_key["shape"] = (1, *data_key["shape"][1:])
        data_key["dtype_str"] = "<u2"
    if "xsx_stream" in doc["data_keys"]:
        data_key = doc["data_keys"]["xsx_stream"]
        data_key["dtype_str"] = "<f8"
        data_key["shape"] = (1, 8, 4096)

    # Ensure dtype_str has the proper numpy format and shape (to pass the EventModel validator)
    for key, val in doc["data_keys"].items():
        if "dtype_str" in val:
            val["dtype_str"] = numpy.dtype(val["dtype_str"]).str
        val["shape"] = tuple(map(lambda x: max(x, 0), val.get("shape", [])))

        # Ensure that laregdatasets are properly shaped to avoid issues with long arrays of chunks
        if ("xs_channel" in key) and (len(val["shape"]) != 3):
            val["shape"] = (1, 6, 4096)

        for key, val in doc["data_keys"].items():
            if ("external" not in val.keys()) \
                and (val.get("dtype") == "array") \
                and ("filename" in key):
                raise NotImplementedError(f"Descriptor with external array data key {key} is not supported.")

    return doc

def patch_datum(doc):
    doc = copy.deepcopy(doc)
    kwargs = doc.get("datum_kwargs", {})

    # Override indices with the point_number if present:
    # Necessary to correctly apply the filename template to tiff files when multiple Resources are present
    point_number = kwargs.pop("point_number", None)
    if point_number is not None:
        kwargs["indices"] = {"start": point_number, "stop": point_number + 1}

    return doc

def patch_resource(doc):
    doc = copy.deepcopy(doc)
    kwargs = doc.get("resource_kwargs", {})

    # Fix the resource path
    root = doc.get("root", "")
    if not doc["resource_path"].startswith(root):
        doc["resource_path"] = os.path.join(root, doc["resource_path"])
    doc["root"] = ""  # root is redundant if resource_path is absolute

    # Fix or add resource parameters
    if doc.get("spec") in ["PIZZABOX_ENC_FILE_TXT", "APB", "APB_TRIGGER"]:
        kwargs.update({"sep": " "})        # Data are in space-separated csv format
    elif doc.get("spec") in ["XSP3", "XSP3X", "AD_HDF5", "AD_HDF5_SWMR_STREAM", "AD_HDF5_SWMR_SLICE", "AD_HDF5_SWMR", "PIL100k_HDF5", "PILATUS_HDF5"]:
        kwargs.update({"dataset": 'entry/instrument/detector/data', "join_method": "concat"})
        kwargs["chunk_shape"] = kwargs.get("chunk_shape", (1, ))
    elif doc.get("spec") in ["AD_TIFF"]:
        kwargs["template"] = "/" + kwargs["template"].lstrip("/")    # Ensure leading slash

    return doc


# Define custom consolidators for Pizzabox data
from bluesky_tiled_plugins.writing.consolidators import CONSOLIDATOR_REGISTRY, ConsolidatorBase

class PizzaBoxConsolidator(ConsolidatorBase):
    supported_mimetypes: set[str] = {"application/x-pizzabox-binary"}

    def validate(self, fix_errors=False) -> list[str]:
        notes = super().validate(fix_errors=fix_errors)

        # Initialize adapter from uris and try to locate missing files
        adapter_class = DEFAULT_ADAPTERS_BY_MIMETYPE[self.mimetype]
        uris = [asset.data_uri for asset in self.assets]
        uri_bin, uri_txt = adapter_class.locate_files(*uris)

        if uri_txt and uris == [uri_bin]:
            if not fix_errors:
                raise ValueError(
                    f"Missing asset for PizzaBox binary metadata file: {uri_txt}"
                )
            else:
                self.assets.append(
                    Asset(data_uri=uri_txt, is_directory=False, parameter="metadata")
                )
                msg = f"Registered missing asset for PizzaBox binary metadata file: {uri_txt.split('/')[-1]}"
                warnings.warn(msg, stacklevel=2)
                notes.append(msg)

        return notes

class CSVConsolidator(ConsolidatorBase):
    supported_mimetypes: set[str] = {"text/csv;header=absent"}
    join_method: Literal["stack", "concat"] = "concat"
    join_chunks: bool = False

    def adapter_parameters(self) -> dict:
        allowed_keys = {
            "comment",
            "delimiter",
            "dtype",
            "encoding",
            "header",
            "names",
            "nrows",
            "sep",
            "skipfooter",
            "skiprows",
            "usecols",
        }
        return {
            k: v
            for k, v in {"header": None, **self._sres_parameters}.items()
            if k in allowed_keys
        }

    def validate(self, fix_errors=False) -> list[str]:
        # CSVConsolidator needs special handling to validate the structure when the data_type is StructDtype.
        # In this case, we need to check that the number of columns, their names and dtypes match.
        # The shape and chunks are also validated.
        # If data_type is BuiltinDtype, we can rely on the base class implementation.

        if isinstance(self.data_type, StructDtype):
            from tiled.adapters.csv import CSVAdapter
            import pyarrow.types as patypes

            uris = [asset.data_uri for asset in self.assets]
            adapter = CSVAdapter.from_uris(
                uris[0], **self.adapter_parameters()
            )  # Initialize from the first file
            column_dtypes = adapter.structure().arrow_schema_decoded.types
            notes = []

            if len(column_dtypes) != len(self.data_type.fields):
                raise ValueError(
                    f"Number of columns mismatch: {len(column_dtypes)} != {len(self.data_type.fields)}"
                )

            # Construct the true StructDtype of the data as read by the adapter
            true_column_names_dtypes = []
            for indx, expected, true_column_dtype in zip(range(len(self.data_type.fields)), self.data_type.fields, column_dtypes):
                if patypes.is_string(true_column_dtype) or patypes.is_large_string(true_column_dtype):
                    _true_dtype = np.array([str(x) for x in adapter.read(indx)]).dtype   # becomes "<Un" dtype
                else:
                    _true_dtype = true_column_dtype.to_pandas_dtype()
                true_column_names_dtypes.append((expected.name, _true_dtype))

            true_numpy_dtype = np.dtype(true_column_names_dtypes)
            true_dtype = StructDtype.from_numpy_dtype(true_numpy_dtype)

            if self.data_type != true_dtype:
                if not fix_errors:
                    raise ValueError(
                        f"dtype mismatch: {self.data_type} != {true_dtype}"
                    )
                else:
                    msg = f"Fixed dtype mismatch: {self.data_type.to_numpy_dtype()} -> {true_numpy_dtype}"  # noqa
                    warnings.warn(msg, stacklevel=2)
                    self.data_type = true_dtype
                    notes.append(msg)

            # Get the shape and chunk shape by reading the first column of the CSV file
            nrows, npartitions = len(adapter.read([0])), adapter.structure().npartitions
            dim0_chunks = list_summands(nrows, math.ceil(nrows / npartitions))
            # If there are multiple files, add their chunks as well
            for uri in uris[1:]:
                adapter = CSVAdapter.from_uris(uri, **self.adapter_parameters())
                nrows, npartitions = (
                    len(adapter.read([0])),
                    adapter.structure().npartitions,
                )
                dim0_chunks = (
                    *dim0_chunks,
                    *list_summands(nrows, math.ceil(nrows / npartitions)),
                )
            # Determine the true shape and chunks for the entire dataset
            true_shape, true_chunks = (sum(dim0_chunks), 1), (dim0_chunks, (1,))

            if self.shape != true_shape:
                if not fix_errors:
                    raise ValueError(f"Shape mismatch: {self.shape} != {true_shape}")
                else:
                    msg = f"Fixed shape mismatch: {self.shape} -> {true_shape}"
                    warnings.warn(msg, stacklevel=2)
                    self._num_rows = true_shape[0]
                    self.datum_shape = (1, 1) if self.join_method == "concat" else (1,)
                    notes.append(msg)

            if self.chunks != true_chunks:
                if not fix_errors:
                    raise ValueError(
                        f"Chunk shape mismatch: {self.chunks} != {true_chunks}"
                    )
                else:
                    if len(true_chunks[0]) == 1 or (
                        len(set(true_chunks[0][:-1])) == 1
                        and (true_chunks[0][-1] <= true_chunks[0][0])
                    ):
                        # Either single chunk or all chunks except possibly the last one are the same (larger) size
                        _chunk_shape = tuple(c[0] for c in true_chunks)
                        msg = f"Fixed chunk shape mismatch: {self.chunk_shape} -> {_chunk_shape}"
                        warnings.warn(msg, stacklevel=2)
                        self.chunk_shape = _chunk_shape
                        self.join_chunks = True
                        notes.append(msg)
                    else:
                        msg = f"Fixed chunk shape mismatch along the leading dimension: {true_chunks[0]}"
                        warnings.warn(msg, stacklevel=2)
                        self.chunks = true_chunks
                        notes.append(msg)

            if self.dims and (len(self.dims) != len(true_shape)):
                if not fix_errors:
                    raise ValueError(
                        "Number of dimension names mismatch for a "
                        f"{len(true_shape)}-dimensional array: {self.dims}"
                    )
                else:
                    old_dims = self.dims
                    if len(old_dims) < len(true_shape):
                        self.dims = (
                            ("time",)
                            + old_dims
                            + tuple(
                                f"dim{i}"
                                for i in range(len(old_dims) + 1, len(true_shape))
                            )
                        )
                    else:
                        self.dims = old_dims[: len(true_shape)]
                    msg = f"Fixed dimension names: {old_dims} -> {self.dims}"
                    warnings.warn(msg, stacklevel=2)
                    notes.append(msg)

        else:
            notes = super().validate(fix_errors=fix_errors)

        return notes

CONSOLIDATOR_REGISTRY.update({'application/x-pizzabox-binary': PizzaBoxConsolidator,
                              'text/csv;header=absent': CSVConsolidator})

# Initialize the Tiled client and the TiledWriter
api_key = os.environ.get("TILED_BLUESKY_WRITING_API_KEY_QAS")
tiled_writing_client_sql = from_uri("https://tiled.nsls2.bnl.gov", api_key=api_key)['qas']['migration']
tiled_writing_client_sql.context.http_client.headers['tiled-qos'] = 'acquisition'
tw = TiledWriter(client = tiled_writing_client_sql,
                 backup_directory="/tmp/tiled_backup",
                 patches = {"descriptor": patch_descriptor,
                            "datum": patch_datum,
                            "resource": patch_resource},
                 spec_to_mimetype= {
                    "AD_HDF5": "application/x-hdf5",
                    "AD_HDF5_SWMR": "application/x-hdf5",
                    "AD_HDF5_SWMR_STREAM": "application/x-hdf5",
                    "AD_HDF5_SWMR_SLICE": "application/x-hdf5",
                    "PIL100k_HDF5": "application/x-hdf5",
                    "PILATUS_HDF5": "application/x-hdf5",
                    "AD_TIFF": "multipart/related;type=image/tiff",
                    "APB": "application/x-pizzabox-binary",
                    "APB_TRIGGER": "application/x-pizzabox-binary",
                    "PIZZABOX_ENC_FILE_TXT": "text/csv;header=absent",
                    "XIA_XMAP_HDF5": "application/x-hdf5;type=xia-xmap",
                    "XSP3": "application/x-hdf5",
                    "XSP3X": "application/x-hdf5",
                 },
                 validate=False,
                #  batch_size=1,    # Uncomment to enable streaming
                 )

# Thread-safe wrapper for TiledWriter
tw = BufferingWrapper(tw)

# Set access tags for TiledWriter
# RE.md["tiled_access_tags"] = (RE.md["data_session"],)   # TODO: this access_tag to be used after DataSecurity is implemented
RE.md["tiled_access_tags"] = ("qas_beamline",)   # This is general QAS access tag

# Subscribe the TiledWriter
RE.subscribe(tw)

