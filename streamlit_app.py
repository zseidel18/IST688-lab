import streamlit as st

lab1_page = st.page('labs/lab1.py', title = 'lab 1')
lab2_page = st.page('labs/lab2.py', title = 'lab 2')

pg = st.navigation([lab1_page, lab2_page])
st.set_page_config(page_title= 'lab manager')
pg.run()