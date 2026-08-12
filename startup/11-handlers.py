print(__file__)

from itertools import product

import pandas as pd
from databroker.assets.handlers import HandlerBase, Xspress3HDF5Handler, XS3_XRF_DATA_KEY
import h5py


fc = 7.62939453125e-05
adc2counts = lambda x: ((int(x, 16) >> 8) - 0x40000) * fc \
        if (int(x, 16) >> 8) > 0x1FFFF else (int(x, 16) >> 8)*fc
enc2counts = lambda x: int(x) if int(x) <= 0 else -(int(x) ^ 0xffffff - 1)


class PizzaBoxAnHandlerTxt(HandlerBase):
    def __init__(self, fpath, chunk_size=0):
        '''
        adds the chunks of data to a list
        This combines the chunks together and ignores the chunk size to speed
            things up.
        '''
        self.data = pd.read_csv(fpath, delimiter = " ", header=None)

        ncols_tot = len(self.data.columns)
        ncols = ncols_tot - 3
        # ncols is additional cols, ncols_tot is ncols + 3
        #print("total columns : {}".format(names))
    
        # now write names for columns
        # for the rest, name them counts0, counts1 etc...
        # create full list of columns
        names =['time (s)', 'time (ns)', 'index']
        names = names + [f'counts{i}' for i in range(ncols)]
        chunk_cols = ['timestamp', 'index'] + [f'volts{j}' for j in range(ncols)]


        self.data.columns = names
        for j in range(ncols):
            self.data[f'volts{j}'] = self.data[f'counts{j}'].apply(adc2counts)

        self.data['timestamp'] = self.data['time (s)'] + 1e-9*self.data['time (ns)']
        self.data = self.data[chunk_cols]


    def __call__(self, chunk_num, column=0):
        '''
        returns specified chunk number/index from list of all chunks created
        '''
        columns = ['timestamp', 'adc']
        if chunk_num == 0:
            df = self.data[['timestamp', f'volts{column}']]
            df.columns = columns
            return df
        else:
            return pd.DataFrame(columns=columns)


class PizzaBoxEncHandlerTxt(HandlerBase):
    def __init__(self, fpath, chunk_size=0):
        '''
        adds the chunks of data to a list
        This combines the chunks together and ignores the chunk size to speed
            things up.
        '''
        keys = ['times', 'timens', 'encoder', 'counter', 'di']
        self.data = pd.read_csv(fpath, delimiter = " ", header=None)
        self.data.columns = keys
        #self.data = pd.read_table(fpath, delim_whitespace=True, comment='#', names=keys, index_col=False)
        self.data['timestamp'] = self.data['times'] + 1e-9 * self.data['timens']
        self.data['encoder'] = self.data['encoder'].apply(lambda x: int(x) if int(x) <= 0 else -(int(x) ^ 0xffffff - 1))
        self.data = self.data[['timestamp', 'counter', 'encoder']]


    def __call__(self, chunk_num):
        '''
        returns specified chunk number/index from list of all chunks created
        '''
        columns = ['timestamp', 'counter', 'encoder']
        if chunk_num == 0:
            return self.data
        else:
            return pd.DataFrame(columns=columns)


# TODO : move upstream
#class PizzaBoxEncHandlerTxt(HandlerBase):
#    encoder_row = namedtuple('encoder_row',
#                             ['ts_s', 'ts_ns', 'encoder', 'index', 'state'])
#    "Read PizzaBox text files using info from filestore."
#    def __init__(self, fpath, chunk_size):
#        self.chunk_size = chunk_size
#        with open(fpath, 'r') as f:
#            self.lines = list(f)
#
#    def __call__(self, chunk_num):
#        cs = self.chunk_size
#        return [self.encoder_row(*(int(v) for v in ln.split()))
#                for ln in self.lines[chunk_num*cs:(chunk_num+1)*cs]]


class PizzaBoxDIHandlerTxt(HandlerBase):
    di_row = namedtuple('di_row', ['ts_s', 'ts_ns', 'encoder', 'index', 'di'])
    "Read PizzaBox text files using info from filestore."
    def __init__(self, fpath, chunk_size):
        self.chunk_size = chunk_size
        with open(fpath, 'r') as f:
            self.lines = list(f)

    def __call__(self, chunk_num):
        cs = self.chunk_size
        return [self.di_row(*(int(v) for v in ln.split()))
                for ln in self.lines[chunk_num*cs:(chunk_num+1)*cs]]


#class PizzaBoxAnHandlerTxt(HandlerBase):
#    ''' Like pizza box handler except each file has two columns
#    '''
#    "Read PizzaBox text files using info from filestore."
#
#    def __init__(self, fpath, chunk_size):
#        self.chunk_size = chunk_size
#        #print("chunk size : {}".format(chunk_size))
#        with open(fpath, 'r') as f:
#            self.lines = list(f)
#        print(fpath)
#        self.ncols = len(self.lines[0].split())
#        print("number of columns is {}".format(self.ncols))
#        self.cols = ['ts_s', 'ts_ns', 'index', 'adc']
#        self.bases = [10, 10, 10, 16]
#        self.encoder_row = namedtuple('encoder_row', self.cols)
#
#    def __call__(self, chunk_num, column=0):
#        cs = self.chunk_size
#        col_index = column + 3
#        # TODO : clean up this logic, maybe use pandas?
#        # need to first look at how isstools parses this
#        return [self.encoder_row(*(int(v, base=b) for v, b in zip((ln.split()[i] for i in [0,1,2,col_index]), self.bases)))
#                for ln in self.lines[chunk_num*cs:(chunk_num+1)*cs]]


class QASXspress3HDF5Handler(Xspress3HDF5Handler):
    def __call__(self, *args, frame=None, **kwargs):
        self._get_dataset()
        shape = self.dataset.shape
        if len(shape) != 3:
            raise RuntimeError(f'The ndim of the dataset is not 3, but {len(shape)}')
        num_channels = shape[1]
        # print(f"{num_channels = }")
        chanrois = [f'CHAN{c}ROI{r}' for c, r in product([1, 2, 3, 4], [1, 2, 3, 4])]
        attrsdf = pd.DataFrame.from_dict(
            {chanroi: self._file['/entry/instrument/detector/']['NDAttributes'][chanroi] for chanroi in chanrois}
        )
        ##print(attrsdf)
        df = pd.DataFrame(data=self._dataset[frame, :, :].T,
                          columns=[f'ch_{n+1}' for n in range(num_channels)])
        #return pd.concat([df]+[attrsdf])
        return df

    def open(self):
        if self._file:
            return

        self._file = h5py.File(self._filename, "r", swmr=True)

db.reg.register_handler('PIZZABOX_AN_FILE_TXT',
                        PizzaBoxAnHandlerTxt, overwrite=True)
db.reg.register_handler('PIZZABOX_ENC_FILE_TXT',
                        PizzaBoxEncHandlerTxt, overwrite=True)
db.reg.register_handler('PIZZABOX_DI_FILE_TXT',
                        PizzaBoxDIHandlerTxt, overwrite=True)
db.reg.register_handler(QASXspress3HDF5Handler.HANDLER_NAME,
                        QASXspress3HDF5Handler, overwrite=True)
