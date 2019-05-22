# -*- coding: utf-8 -*-
"""
Created on Mon May  6 11:16:32 2019

@author: Jake Welch
"""

from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
import dill

comp_vect = TfidfVectorizer(tokenizer=lambda doc: doc, lowercase=False)

comp_trans = comp_vect.fit_transform(comp_groupby['TERMS'])

comp_dict = dict()

vect_names = comp_vect.get_feature_names()
vect_range = np.arange(0,len(vect_names))

for i in range(len(vect_range)):
    comp_dict[vect_range[i]] = vect_names[i]
    
trans_inds = comp_trans.indices
trans_vals = comp_trans.data

final_dict = dict()

for j in range(len(trans_inds)):
    final_dict[comp_dict[trans_inds[j]].upper()] = trans_vals[j]
    
dill.dump(final_dict,open('final_dict','wb'))