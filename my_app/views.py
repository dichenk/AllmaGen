from django.shortcuts import render
from django.http import JsonResponse
import pandas as pd
import matplotlib.pyplot as plt


def main_page(request):
    return render(request, 'index.html')

def ctrChart(request):
    interval = request.GET.get('interval', 'D')
    click_type = request.GET.get('clickType', 'click')

    ctr = get_ctr(interval, click_type)

    data = {
        'dates': list(ctr.index.strftime('%Y-%m-%d')),
        'ctr_values': list(ctr.values)
    }
    return JsonResponse(data)

def evpmChart(request):
    interval = request.GET.get('interval', 'D')
    event_type = request.GET.get('eventType', 'fclick')

    evpm = get_evpm(interval, event_type)

    data = {
        'dates': list(evpm.index.strftime('%Y-%m-%d')),
        'evpm_values': list(evpm.values)
    }
    return JsonResponse(data)

def get_ctr(grouping_interval='3H', click_type='click'):

    data_y = pd.read_csv('static/interview.data/interview.y.csv')
    data_x = pd.read_csv('static/interview.data/interview.X.csv')

    data_x = data_x.sort_values(by='reg_time').drop_duplicates(subset='uid', keep='first')

    # Заполнение пропущенных значений в столбцах osName, model, hardware значением "DoNotKnow"
    columns_to_fill = ['osName', 'model', 'hardware']
    for col in columns_to_fill:
        data_x[col].fillna("DoNotKnow", inplace=True)

    # Извлечение 2 значащих блоков из столбца uid
    data_x['uid'] = data_x['uid'].apply(lambda x: '-'.join(x.split('-')[3:]))
    data_y['uid'] = data_y['uid'].apply(lambda x: '-'.join(x.split('-')[3:]))

    # Преобразование столбца reg_time в формат datetime и установка его в качестве индекса
    data_x.set_index('reg_time', inplace=True, drop=False)
    data_x.index = pd.to_datetime(data_x.index)

    # Группировка данных из interview.x по заданному интервалу и подсчет уникальных uid
    grouped_x = data_x.resample(grouping_interval)['uid'].nunique()

    # Фильтрация данных из interview.y для событий fclick и click-through
    if click_type == 'click':
        uids_with_other_events = data_y[data_y['tag'].isin(['content', 'lead', 'misc', 'registration', 'signup'])]['uid'].unique()
        uids_with_only_fclick = data_y[(data_y['tag'] == 'fclick') & (~data_y['uid'].isin(uids_with_other_events))]['uid'].unique()
        filtered_y = data_y[(data_y['uid'].isin(uids_with_only_fclick)) & (data_y['tag'] == 'fclick')]
    elif click_type == 'clickPlus':
        uids_with_fclick = data_y[data_y['tag'] == 'fclick']['uid'].unique()
        filtered_y = data_y[(data_y['uid'].isin(uids_with_fclick)) & (data_y['tag'] == 'fclick')]
    elif click_type == 'clickMinus':
        uids_with_fclick = data_y[data_y['tag'] == 'fclick']['uid'].unique()
        uids_with_other_events = data_y[data_y['tag'].isin(['content', 'lead', 'misc', 'registration', 'signup']) & data_y['uid'].isin(uids_with_fclick)]['uid'].unique()
        filtered_y = data_y[(data_y['uid'].isin(uids_with_other_events)) & (data_y['tag'] == 'fclick')]


    # Соединение данных из двух файлов по uid
    merged_y = pd.merge(filtered_y, data_x[['uid', 'reg_time']], on='uid', how='inner').set_index('reg_time')
    merged_y.index = pd.to_datetime(merged_y.index)

    # Группировка объединенных данных по заданному интервалу и подсчет уникальных uid
    grouped_y = merged_y.resample(grouping_interval)['uid'].nunique()

    # Расчет CTR для каждого интервала
    ctr = (grouped_y / grouped_x * 100).fillna(0)
    
    return ctr

def get_evpm(grouping_interval='3H', event_type='fclick'):
    data_y = pd.read_csv('static/interview.data/interview.y.csv')
    data_x = pd.read_csv('static/interview.data/interview.X.csv')

    data_x = data_x.sort_values(by='reg_time').drop_duplicates(subset='uid', keep='first')
    columns_to_fill = ['osName', 'model', 'hardware']
    for col in columns_to_fill:
        data_x[col].fillna("DoNotKnow", inplace=True)

    data_x['uid'] = data_x['uid'].apply(lambda x: '-'.join(x.split('-')[3:]))
    data_y['uid'] = data_y['uid'].apply(lambda x: '-'.join(x.split('-')[3:]))

    data_x.set_index('reg_time', inplace=True, drop=False)
    data_x.index = pd.to_datetime(data_x.index)
    grouped_x = data_x.resample(grouping_interval)['uid'].nunique()

    # Фильтрация данных из interview.y на основе event_type
    if event_type == 'fclick':
        filtered_y = data_y[data_y['tag'] == 'fclick']
    elif event_type == 'content':
        filtered_y = data_y[data_y['tag'].isin(['content', 'vcontent'])]
    elif event_type == 'registration':
        filtered_y = data_y[data_y['tag'].isin(['registration', 'vregistration'])]
    elif event_type == 'signup':
        filtered_y = data_y[data_y['tag'].isin(['signup', 'vsignup'])]
    elif event_type == 'lead':
        filtered_y = data_y[data_y['tag'].isin(['lead', 'vlead'])]
    elif event_type == 'other':
        filtered_y = data_y[~data_y['tag'].isin(['fclick', 'content', 'vcontent', 'registration', 'vregistration', 'signup', 'vsignup', 'lead', 'vlead'])]

    merged_y = pd.merge(filtered_y, data_x[['uid', 'reg_time']], on='uid', how='inner').set_index('reg_time')
    merged_y.index = pd.to_datetime(merged_y.index)
    grouped_y = merged_y.resample(grouping_interval)['uid'].nunique()

    evpm = (grouped_y / grouped_x * 1000).fillna(0)
    
    return evpm
