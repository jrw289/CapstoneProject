# -*- coding: utf-8 -*-
"""
Created on Mon May 20 11:51:20 2019

@author: Jake Welch
"""

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
import dill
import re



#Function to check if company is part of this list of pre-filtered companies
def filterByCompany(company,cdf,comp_list):
    
    check = [company in y for y in comp_list]
    
    if any(check):
        comp_mask = [company in x for x in cdf.ORG]
        return cdf[comp_mask]
    else:
        return [0]

#Function to check for companies with the expected topics
def filterByTopic(topic,cgb,dicts):
    
    if any([topic in y for y in list(dicts.keys())]):
        
        topic_mask = cgb['TERMS'].apply(lambda x: any([topic in z for z in x])) 
        return cgb[topic_mask]
   
    else:
        
        return pd.DataFrame()
        
#Function for recommending other companies working on similar projects 
def recommendSystem(company,cgb,dicts):
    
    #NEEDS EXACT COMPANY NAME 
    temp_row = cgb[cgb.ORG == company]
    
    temp_set = temp_row['TERMS'].iloc[0]
    cgb['MATCHES'] = cgb['TERMS'].apply(lambda x: x & temp_set)
    cgb['MATCH_LEN'] = cgb['MATCHES'].apply(lambda x: sum([dicts[y] for y in x]))
    cgb = cgb.sort_values(by='MATCH_LEN',ascending=False)
    
    if len(cgb['ORG']) > 6:
        return (cgb['ORG'][1:6])
    else:
        return (cgb['ORG'])

#Feed a DataFrame, produce a DataFrame with more useful separation of money
#Older method was more involved, but now it works more simply
def frMoneySplitter(df):

    temp_df = df.groupby('fy').sum()
    temp_pairs = pd.DataFrame(temp_df['totalCostAmount'])
    temp_df = df.groupby('fy').count()
    temp_pairs['count'] = pd.DataFrame(temp_df['title'])
    temp_pairs.columns = ['total','grants']
    
    return temp_pairs

#API Calls to the Federal Reporter API
#@retry(stop_max_attempt_number=10)
def frReq(org, pms):

    pms = {
           'offset': 0,
           'limit': 50
           }

    url = 'https://api.federalreporter.nih.gov/v1/projects/search?query=orgName:{}'.format(org)
    fr_req = req.get(url,params=pms)
    
    if str(fr_req) == '<Response [200]>':  
        fr_json = fr_req.json()
        fr_data = pd.DataFrame(fr_json['items'])
        
        if fr_json['totalCount'] > fr_json['limit']:
            new_offset = fr_json['limit'] + 1
            fr_json_temp = fr_json
            
            while len(fr_json_temp['items']) == fr_json_temp['limit']:
                pms = {
                        'offset': new_offset,
                        'limit': fr_json_temp['limit']
                        }
                fr_req_temp = req.get(url,params=pms)
                fr_json_temp = fr_req_temp.json()
                fr_data_temp = pd.DataFrame(fr_json_temp['items'])
                fr_data = pd.concat([fr_data,fr_data_temp],ignore_index=True)
                new_offset = new_offset + fr_json_temp['limit']
        
        if not fr_data.empty:
            return fr_data
        else:
            return fr_data
    
    else:
        return pd.DataFrame()

#Function for plotting the Bokeh images of the Federal Reporter grant data 
def frPlot(frData,orgName):

    fr_axes = frMoneySplitter(frData)
    fr_axes = fr_axes.rename_axis('year',axis=0)
    
    source = ColumnDataSource(data = fr_axes)

    tooltips = [
            ('Year','<strong>@year</strong>'),
            ("Total", "<strong>$@total{0,0}</strong>"),
            ("# of Grant", "<strong>@grants</strong>")
             ]
        
    p = figure(title=orgName + ' GRANT MONEY',x_axis_label='YEAR',y_axis_label='FUNDING ($)',
               x_range=(fr_axes.index.min()-1,fr_axes.index.max()+1),tooltips=tooltips,
               tools=['hover'], plot_width=500,plot_height=550)

    p.vbar('year',top='total',width=0.9,source=source)
    
    p.title.text_font_size = "18pt"
    p.xaxis.axis_label_text_font_size = "16pt"
    p.yaxis.axis_label_text_font_size = "16pt"
    p.xaxis.major_label_text_font_size = "12pt"
    p.yaxis.major_label_text_font_size = "12pt"
    p.yaxis[0].formatter = NumeralTickFormatter(format="0,0")
    p.toolbar.logo = None
    p.toolbar_location = None
    
    source, div = components(p)
    resources = INLINE.render()
    
    return p

#API Calls to the USPTO API
@retry(stop_max_attempt_number=10)
def usptoReq(orgName,uspto_pms):
    
    #Grab all the USPTO lines which mention the company name
    uspto_req = req.get('https://developer.uspto.gov/ibd-api/v1/patent/application?',
                    params=uspto_pms)
    
    if str(uspto_req) == '<Response [200]>':
        
        uspto_json = uspto_req.json()
        uspto_num = uspto_json['response']['numFound']
        uspto_start = uspto_json['response']['start']
        uspto_data = pd.DataFrame(uspto_json['response']['docs'])

        if uspto_num > int(uspto_pms['rows']):
        
            new_uspto_offset = uspto_start + int(uspto_pms['rows'])
            uspto_temp = uspto_data
             
            while len(uspto_data) < uspto_num:
                uspto_pms = {
                             'start': new_uspto_offset,
                             'searchText':orgName,
                             'rows': uspto_pms['rows']
                             } 
                uspto_req_temp = req.get('https://developer.uspto.gov/ibd-api/v1/patent/application?',
                                         params=uspto_pms)
                
                uspto_json_temp = uspto_req_temp.json()
                uspto_data_temp = pd.DataFrame(uspto_json_temp['response']['docs'])
                
                uspto_data = pd.concat([uspto_data,uspto_temp],ignore_index=True)                
                new_uspto_offset = new_uspto_offset + int(uspto_pms['rows'])



        if not uspto_data.empty:
            #
#            uspto_data = uspto_data[uspto_data.applicant.notnull()]
#            uspto_data['refined'] = uspto_data['applicant'].apply(lambda x: [y.upper() for y in x])
#            uspto_data['hasOrgName'] = uspto_data['refined'].apply(lambda x: any([y in orgName for y in x]))
#            uspto_data['hasOrgName2'] = uspto_data['refined'].apply(lambda x: any([orgName in y for y in x]))
#            uspto_data_refined = uspto_data[uspto_data.hasOrgName | uspto_data.hasOrgName2].sort_values(by=['applicationNumber',
#                                                                               'documentDate'])

                        

            #Previous method looks for the identical names between the returned field and the orgName
            #However, it had trouble handling minor differences in puncuation
            #Can implement a reg-exp method to strip away the non-alphanumerical characters:  
            uspto_data = uspto_data[uspto_data.applicant.notnull()]
            uspto_data['refined'] = uspto_data['applicant'].apply(lambda x: [y.upper() for y in x])
            uspto_data['refined'] = uspto_data['refined'].apply(lambda x: [re.sub(r'\W+', '', y) for y in x])
            temp_orgName = re.sub(r'\W+', '', orgName)
            
            uspto_data['hasOrgName'] = uspto_data['refined'].apply(lambda x: any([y in temp_orgName for y in x]))
            uspto_data['hasOrgName2'] = uspto_data['refined'].apply(lambda x: any([temp_orgName in y for y in x]))
            uspto_data_refined = uspto_data[uspto_data.hasOrgName | uspto_data.hasOrgName2].sort_values(by=['applicationNumber',
                                                                               'documentDate'])

    
    

            uspto_final = uspto_data_refined[uspto_data_refined.year.notnull()]    
            return uspto_final
        
        else:
            return uspto_data
    else:
        return pd.DataFrame()

#Function for plotting the Bokeh images of the USPTO grant data 
def usptoPlot(uspto_final,orgName):
    
    uspto_dict = dict()
    uspto_dict['application'] = 0
    uspto_dict['grant'] = 1
    
    uspto_final = uspto_final.drop_duplicates(['_version_','applicationDate',
                                'applicationNumber','applicationType','documentId',
                                'documentType','productionDate','publicationDate','title','year'])
    
    uspto_final['year'] = uspto_final['year'].astype('int')
    uspto_final['type_ind'] = uspto_final['documentType'].apply(lambda x: uspto_dict[x])
    
    source_2 = ColumnDataSource(data = uspto_final)

    tooltips_2 = [
            ("Title", "<strong>@title</strong>"),
            ("Application Date", "@applicationDate"),
            ("Application Type", "@applicationType"),
            ("Document Type", "@documentType"),    
            ("Patent Number", "@patentNumber"),
            ("Publication Date", "@publicationDate"),
            ("year", "@year")  
            ]
    
    grant_types = ['application','grant']
    
    p = figure(title=orgName + ' PATENTS',y_axis_label='YEAR',x_axis_label='PATENT',
               y_range=(int(uspto_final.year.min())-1,int(uspto_final.year.max())+1),
               x_range=grant_types, tooltips=tooltips_2, tools=['hover','tap'], 
               plot_width=500,plot_height=550)
    
    url = "@pdfPath"
    taptool = p.select(type=TapTool)
    taptool.callback = OpenURL(url=url)

    color_mapper = CategoricalColorMapper(factors=list(uspto_final['title'].unique()),
                                          palette=all_palettes['Set1'][9])

    p.scatter(x='documentType',y=jitter('year',0.5), size=10,
              source=source_2, alpha=0.5,color={'field':'title','transform':color_mapper})

    p.title.text_font_size = "18pt"
    p.xaxis.axis_label_text_font_size = "16pt"
    p.yaxis.axis_label_text_font_size = "16pt"
    p.xaxis.major_label_text_font_size = "12pt"
    p.yaxis.major_label_text_font_size = "12pt"
    p.toolbar.logo = None
    p.toolbar_location = None

    source, div = components(p)
    resources = INLINE.render()
    
    return p
