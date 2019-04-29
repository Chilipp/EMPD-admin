# Common functions for the EMPD-admin modules
import pandas as pd
import numpy as np


def read_empd_meta(fname):
    fname = fname

    ret = pd.read_csv(str(fname), sep='\t', index_col='SampleName',
                      dtype=str)

    for col in ['Latitude', 'Longitude', 'Elevation', 'AreaOfSite', 'AgeBP']:
        if col in ret.columns:
            ret[col] = ret[col].replace('', np.nan).astype(float)
    if 'ispercent' in ret.columns:
        ret['ispercent'] = ret['ispercent'].replace('', False).astype(bool)

    if 'okexcept' not in ret.columns:
        ret['okexcept'] = ''

    return ret
