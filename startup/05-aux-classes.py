print(__file__)
from bluesky.callbacks.mpl_plotting import LivePlot

def print_now():
    return datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S.%f')



class NormPlot(LivePlot):
    def __init__(self, num_name, den_name, result_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.num_name = num_name
        self.den_name = den_name
        self.result_name = result_name
                     
    def event(self, doc):                    
        doc = dict(doc)
        doc['data'] = dict(doc['data'])
        try:
            if self.den_name == '1':
                denominator = 1
            else:
                denominator = doc['data'][self.den_name]
            doc['data'][self.result_name] = doc['data'][self.num_name] / denominator
        except KeyError:
            pass
        super().event(doc)

