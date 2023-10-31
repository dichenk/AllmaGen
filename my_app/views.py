import io
import logging

import pandas as pd
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render


s_logger = logging.getLogger('chat')


X_FILE = 'static/interview.data/interview.X.csv'
Y_FILE = 'static/interview.data/interview.y.csv'


def main_page(request):
    s_logger.debug("called main page")
    return render(request, 'index.html')


def ctrChart(request):
    s_logger.debug("called ctrChart")
    interval = request.GET.get('interval', 'D')
    click_type = request.GET.get('clickType', 'click')

    ctr = get_ctr(interval, click_type)

    data = {
        'dates': list(ctr.index.strftime('%Y-%m-%d')),
        'ctr_values': list(ctr.values)
    }
    return JsonResponse(data)


def evpmChart(request):
    s_logger.debug("called evpmChart")
    interval = request.GET.get('interval', 'D')
    event_type = request.GET.get('eventType', 'fclick')

    evpm = get_evpm(interval, event_type)

    data = {
        'dates': list(evpm.index.strftime('%Y-%m-%d')),
        'evpm_values': list(evpm.values)
    }
    return JsonResponse(data)


def get_ctr(grouping_interval='3H', click_type='click'):
    s_logger.debug("called get_ctr")
    cache_key = f'ctr_{grouping_interval}_{click_type}'
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    s_logger.debug("get_ctr step 1")

    data_x, data_y = get_data_x(), get_data_y()
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
        uids_with_other_events = (
            data_y[
                data_y['tag'].isin(['content', 'lead', 'misc', 'registration', 'signup']) &
                data_y['uid'].isin(uids_with_fclick)
            ]['uid'].unique()
        )
        filtered_y = data_y[
            (data_y['uid'].isin(uids_with_other_events)) &
            (data_y['tag'] == 'fclick')
            ]

    s_logger.debug("get_ctr step 2")

    # Соединение данных из двух файлов по uid
    merged_y = pd.merge(filtered_y, data_x.reset_index()[['uid', 'reg_time']], on='uid', how='inner').set_index('reg_time')
    merged_y.index = pd.to_datetime(merged_y.index)

    grouped_x = data_x.resample(grouping_interval).sum()
    grouped_y = merged_y.resample(grouping_interval).nunique()

    ctr = aggregate_data(
        grouped_x,
        grouped_y,
        grouped_x.index,
        'impressions',
        already_grouped=True)*100

    cache.set(cache_key, ctr, 3600)
    return ctr


def get_evpm(grouping_interval='3H', event_type='fclick'):
    s_logger.debug("called get_evpm")
    cache_key = f'evpm_{grouping_interval}_{event_type}'
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    data_x, data_y = get_data_x(), get_data_y()
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

    merged_y = pd.merge(filtered_y, data_x.reset_index()[['uid', 'reg_time']], on='uid', how='inner').set_index('reg_time')
    merged_y.index = pd.to_datetime(merged_y.index)

    grouped_x = data_x.resample(grouping_interval).sum()
    grouped_y = merged_y.resample(grouping_interval).nunique()

    evpm = aggregate_data(
        grouped_x,
        grouped_y,
        grouped_x.index,
        'impressions',
        already_grouped=True)*1000

    cache.set(cache_key, evpm, 3600)
    return evpm


def get_data_x():
    s_logger.debug("called get_data_x")
    cached_data_x = get_cached_dataframe('data_x_cache_key')
    if cached_data_x is not None:
        return cached_data_x
    data_x = pd.read_csv(X_FILE)
    data_x = (data_x.sort_values(by='reg_time')
              .drop_duplicates(subset='uid', keep='first'))
    # Заполнение пропущенных значений в столбцах значением "DoNotKnow"
    columns_to_fill = ['osName', 'model', 'hardware']
    for col in columns_to_fill:
        data_x[col].fillna("DoNotKnow", inplace=True)
    # Извлечение 2 значащих блоков из столбца uid
    data_x['uid'] = data_x['uid'].apply(lambda x: '-'.join(x.split('-')[3:]))
    # reg_time в формат datetime и установка его в качестве индекса
    data_x.set_index('reg_time', inplace=True)
    data_x.index = pd.to_datetime(data_x.index)
    # Создание нового столбца, который учитывает fc_imp_chk
    data_x['impressions'] = data_x['fc_imp_chk'] + 1
    cache_dataframe('data_x_cache_key', data_x, 48*60*60)
    return data_x


def get_data_y():
    s_logger.debug("called get_data_y")

    cached_data_y = get_cached_dataframe('data_y_cache_key')
    if cached_data_y is not None:
        return cached_data_y
    
    data_y = pd.read_csv(Y_FILE)
    # Извлечение 2 значащих блоков из столбца uid
    data_y['uid'] = data_y['uid'].apply(lambda x: '-'.join(x.split('-')[3:]))
    cache_dataframe('data_y_cache_key', data_y, 48*60*60)
    return data_y


def aggregate_data(
        data_x,
        merged_y,
        group_column,
        metric_column,
        already_grouped=False):
    s_logger.debug("called aggregate_data")
    if not already_grouped:
        grouped_x = data_x.groupby(group_column)[metric_column].sum()
        grouped_y = merged_y.groupby(group_column)['uid'].nunique()
    else:
        grouped_x = data_x[metric_column]
        grouped_y = merged_y['uid']

    result = (grouped_y / grouped_x).fillna(0)
    return result


def cache_dataframe(key, df, timeout):
    s_logger.debug("called cache_dataframe")
    buffer = io.BytesIO()
    df.to_pickle(buffer)
    cache.set(key, buffer.getvalue(), timeout)


def get_cached_dataframe(key):
    s_logger.debug("called get_cached_dataframe")
    cached_data = cache.get(key)
    if cached_data is None:
        return None
    buffer = io.BytesIO(cached_data)
    return pd.read_pickle(buffer)
