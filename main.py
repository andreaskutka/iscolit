# ---- LOAD PACKAGES ----
import math
from datetime import date, timedelta, timezone
import yaml

import streamlit as st
import psycopg2
import pandas as pd
import streamlit_authenticator as stauth
from deta import Deta

# ---- PAGE CONFIG ----
st.set_page_config(page_title='Shaviyani ISIC Labelling',
                   page_icon=':bar_chart:',
                   layout='wide',
                   initial_sidebar_state='collapsed')

# ---- GET USERS FROM DETA ----
#deta_key = st.secrets["deta_key"]
#deta = Deta(deta_key)
#db = deta.Base('users')
#res = db.fetch()
#users = res.items

# ---- AUTHENTICATION  ----
#credentials = {'usernames': {user['key']: {'name': user['key'], 'password' : user['password']} for user in users}}
#authenticator = stauth.Authenticate(credentials, cookie_name='isco-dash', key='arndkee', cookie_expiry_days=30)

# login form and messages
#name, authentication_status, username = authenticator.login('Login', 'main')

#if authentication_status == False:
#    st.error('Username or password is incorrect.')

#if authentication_status == None:
#    st.warning('Please enter your username and password.')

#if authentication_status:

# ---- PULL DATA AND CASHE----
#   @st.experimental_memo # remove loading data into cashe
def pull_data():
    connection = psycopg2.connect(
        host="dpg-ccur4ml3t398cofk19l0-a.oregon-postgres.render.com",
        database="labelling",
        user=st.secrets["dbuser"],
        password=st.secrets["dbpw"]
    )
    with connection as conn:
        sql = "select status,date, username, filename, batch from isco_labelling.sentences_sentence left join isco_labelling.auth_user au on reviewer_id = au.id"
        data = pd.read_sql_query(sql, conn)
    return data

with st.spinner("Wait for it, we're getting the latest data..."):
    data = pull_data()

# ---- SIDEBAR ----
#authenticator.logout('Logout', 'sidebar')
#st.sidebar.title(f'Hi there, {name}!')
st.sidebar.header('Configurations')

remove_users = ['andreas.kutka@rowsquared.com', 'peter.brueckmann@rowsquared.com', 'gabriele.tani@rowsquared.com', 'admin']
all_users = data['username'].unique()
actual_users = [x for x in all_users if x not in remove_users]
selected_users = st.sidebar.multiselect(
    "Select the users:",
    options= all_users,
    default = actual_users
)
data = data.query('username == @selected_users')

cutoff = st.sidebar.number_input(
    'Ignore days with n < x sentences processed',
    value=10
)

# calculate some
processed = data[data['status'] == 'processed']
proc_grp_day = processed.groupby([processed['date'].dt.date])
count_by_day = pd.DataFrame({'count':proc_grp_day.size()})
days_worked = proc_grp_day.size().where(lambda x: x > cutoff).dropna().count()

past_days = st.sidebar.slider(
    'Number of working days for processing rate',
    value=3,
    min_value=1,
    max_value=int(days_worked)
)
radio = st.sidebar.radio(
    "Select data source for total sentences",
    ('Assigned data', 'Custom number')
)
if radio == 'Assigned data':
    total_tot = data.shape[0]
else:
    total_tot = st.sidebar.number_input(
        'Write custom total number of sentences',
        value=242802,
    )
# ---- PREP VARIABLES ----
proc_tot = processed['status'].count()


p3d = proc_grp_day.size().where(lambda x: x > 10).dropna().loc[: date.today() - timedelta(days=1)].iloc[-1*past_days:]
if p3d.shape[0] > 0:
    proc_p3d_mean = round(p3d.mean())
    proc_p3d_per = round(proc_p3d_mean/total_tot*100, 1)
    days_projected = math.ceil((total_tot - proc_tot)/proc_p3d_mean)
else:
    proc_p3d_mean = math.nan
    proc_p3d_per = math.nan
    days_projected = math.inf

unpro_tot = data[data['status'] == 'unprocessed'].shape[0]
viewed_tot = data[data['status'] == 'viewed'].shape[0]

proc_tot_per = round(proc_tot / total_tot * 100, 1)
viewed_per = round(viewed_tot / total_tot * 100, 1)
unpro_per = round(unpro_tot / total_tot * 100, 1)


# get time ago string
def pretty_date(time=False):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    from datetime import datetime
    now = datetime.now().replace(tzinfo=timezone.utc)
    if type(time) is int:
        diff = now - datetime.fromtimestamp(time)
    elif isinstance(time, datetime):
        diff = now - time
    elif not time:
        diff = 0
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return str(second_diff) + " seconds ago"
        if second_diff < 120:
            return "a minute ago"
        if second_diff < 3600:
            return str(second_diff // 60) + " minutes ago"
        if second_diff < 7200:
            return "an hour ago"
        if second_diff < 86400:
            return str(second_diff // 3600) + " hours ago"
    if day_diff == 1:
        return "Yesterday"
    if day_diff < 7:
        return str(day_diff) + " days ago"
    if day_diff < 31:
        return str(day_diff // 7) + " weeks ago"
    if day_diff < 365:
        return str(day_diff // 30) + " months ago"
    return str(day_diff // 365) + " years ago"

lastaction=pretty_date(data.nlargest(1, columns='date')['date'].iloc[0])

# ---- MAIN PAGE ----

st.title('Shaviyani ISCO Labelling')
st.write('')
st.write(f'Last action by classifiers: {lastaction}')
# ---- MAIN METRICS -----

left_column, middle_column, right_column = st.columns(3)
with left_column:
    st.metric(label="Processed in total", value=f'{proc_tot:,} ({proc_tot_per} %)')
    st.metric(label="Unprocessed", value=f'{unpro_tot:,} ({unpro_per} %)')

with middle_column:
    st.metric(
        label=f'Mean processing rate in past {past_days} days',
        value=f'{proc_p3d_mean:,} ({proc_p3d_per} %)'
    )
    st.metric(label="Viewed", value=f'{viewed_tot:,} ({viewed_per} %)')

with right_column:
    st.metric(
        label='Number of days worked / remaining',
        value=f'{days_worked} / {days_projected}'
    )
    st.metric(label="Total", value=f'{total_tot:,}')

# ---- BAR CHART, PROCESSED BY DAY ----
st.write('')
st.subheader('# sentences processed by day')
st.bar_chart(count_by_day)

# ---- TABLE, PROCESSED BY USER AND DAY ----
by_user_by_day = processed.groupby([processed['date'].dt.date, 'username']).size().unstack(0, fill_value=0)
st.write('')
st.subheader('# sentences processed by user by day')
st.dataframe(by_user_by_day)

# ---- COUNT BY USER AND STATUS
st.write('')
st.subheader('# unprocessed/viewed sentences by user ')

left_col, right_col = st.columns([1, 3])

with left_col:
    by_user_by_status = data.groupby(['status', 'username']).size().unstack(0, fill_value=0)

    st.dataframe(by_user_by_status)

with right_col:
    by_user_by_status_df = data.groupby(['status', 'username'], as_index=False).size()
    rem_status = [x for x in ['unprocessed', 'viewed'] if x in data['status'].unique()]
    st.bar_chart(by_user_by_status, y=rem_status)

# FILENAME
st.subheader('# cases uploaded by filename')
batx = st.selectbox(
    'Select batch',
    options=data['batch'].unique()
)
by_filename = data.query('batch == @batx').groupby(['filename']).size()
st.dataframe(by_filename)
