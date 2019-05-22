# -*- coding: utf-8 -*-
"""
Created on Thu Apr 25 12:31:04 2019

@author: Jake Welch
"""

from flask import Flask, request, render_template, jsonify
from jinja2 import Template
import dill

from bokeh.palettes import Inferno11, Paired11, all_palettes
from bokeh.models import ColumnDataSource, OpenURL, TapTool, NumeralTickFormatter, CategoricalColorMapper
from bokeh.plotting import figure, show
from bokeh.layouts import row
from bokeh.embed import components
from bokeh.resources import INLINE
from bokeh.transform import jitter

import requests as req 
import pandas as pd
import numpy as np
from retrying import retry 

######################################################################################

#This company has an interesting history 
#orgName = 'GAIA MEDICAL INSTITUTE LLC'

app = Flask(__name__)

from cap_funcs import *
    
#All the grant data for the companies 
comp_data = pd.read_csv('Constructed_companies_list.csv')

#TF-IDF dictionary based on the grant terms in this corpus 
final_dict = dill.load(open('final_dict','rb'))
    
#Combine all grants by company, taking all terms associated with all their grants into a single list
#Then perform some basic string operations to clean them up and leave them as sets 
comp_groupby = comp_data.groupby('ORG').agg(lambda x: tuple(x)).applymap(list).reset_index()
comp_groupby['PROJECT_TERMS_2'] = comp_groupby['PROJECT_TERMS'].apply(lambda x: [str(y).upper().split('; ') for y in x])
comp_groupby['TERMS'] = comp_groupby['PROJECT_TERMS_2'].apply(lambda x: set([y.strip() for i in x for y in i]))
comp_groupby = comp_groupby.drop(columns = ['SPLIT_TERMS','PROJECT_TERMS','PROJECT_TERMS_2'])

#These are some companies which are too big to really consider purchasing
#   and work on wide-ranging problems so they clog up the recommendation engine
#These are specifically filtered out in this case
filt_comps = ['GEORGIA TECH RESEARCH CORPORATION','PALO ALTO INSTITUTE FOR RES & EDU INC',
              'LEIDOS BIOMEDICAL RESEARCH, INC.','BROAD INSTITUTE INC','ROSWELL PARK CANCER INSTITUTE CORP',
              'RAND CORPORATION']

comp_groupby = comp_groupby[~(comp_groupby.ORG.isin(filt_comps))]

#These are the remaining companies, which are used for one of the filters 
comp_list = sorted(comp_groupby['ORG'].unique().tolist())


#Page for plotting the graph
#For some reason, will not work as an HTML file with identical code
template = Template('''<!DOCTYPE html>
<link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css" integrity="sha384-ggOyR0iXCbMQv3Xipma34MD+dH/1fQ784/j6cY/iJTQUOhcWr7x9JvoRxT2MZw1T" crossorigin="anonymous">
<html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Plots</title>
        {{ resources }}
        {{ script }}
        <style>
            .embed-wrapper {
                display: flex;
                justify-content: space-evenly;
            }
        </style>
    </head>
    <body>
        <div class="embed-wrapper">
            {% for key in div.keys() %}
                {{ div[key] }}
            {% endfor %}
        </div>
<h4><div align="center">
    Recommended other companies to explore:
</div></h4>

     <ul style='list-style:none'>
      {% for name in options %}
      <li align='center'> <a href='/charts?comp_name={{name.replace(' ','+')}}'> {{ name }} </a></li>
      {% endfor %}
      </ul>

    </body>
</html>
''')
    
#Home call
@app.route('/',methods=['GET'])
def index():
    if request.method == 'GET':
        return render_template('home.html')


#Code the topics calls
@app.route('/topics',methods=['GET'])
def topics():
    
    if request.method == 'GET':

        topic = request.args.get('topic_name')
        options = filterByTopic(topic.upper(),comp_groupby,final_dict)

        if not (options.empty): 
            
            return render_template('topics.html',topic=topic.upper(),options=options['ORG'])
        
        else:
            
            return render_template('topics.html',topic=topic.upper(),options=options)
        
    else:
        
        return render_template('error_t.html')

#Code for the charts calls 
@app.route('/charts',methods=['GET'])
def charts():
    if request.method == 'GET':
        
        orgName = str(request.args.get('comp_name')).upper()
        filt = filterByCompany(orgName,comp_groupby,comp_list)
        
        if any(filt):    
            
            params = {
                      'limit':50
                      }     
            
            fr_data = frReq(orgName,params)                       
            
            uspto_params={
                          'searchText':orgName,
                          'rows':'100'
                          }
            
            uspto_data = usptoReq(orgName,uspto_params)            

            if (not uspto_data.empty) & (not fr_data.empty):
                p_fr = frPlot(fr_data,orgName)
                p_us = usptoPlot(uspto_data,orgName)
                plots = {'Federal RePORTER':p_fr,'US Patent and Trade':p_us}
                
            elif (not fr_data.empty):
                plots = {'Federal RePORTER':frPlot(fr_data,orgName)}
                
            else:
                return render_template('error_c.html')
            
            script, div = components(plots)
            resources = INLINE.render()            
            
            options = recommendSystem(orgName,comp_groupby,final_dict)

            return template.render(resources=resources,script=script,div=div,options =options)

        else: 
            return render_template('error_c.html')

if __name__ == '__main__':
    app.run()