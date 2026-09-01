import streamlit as st

lab1_page = st.Page('labs/lab1.py', title = 'lab 1')
lab2_page = st.Page('labs/lab2.py', title = 'lab 2', default=True)

pg = st.navigation([lab1_page, lab2_page])
st.set_page_config(page_title= 'lab manager')
pg.run()