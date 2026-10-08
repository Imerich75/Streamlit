import streamlit as st

# The traffic map is the only page. Old links to the former multipage URL
# (/Forgalmi_Terkep) are served by the same script instead of "Page not found".
page = "forgalmi_terkep.py"
st.navigation(
    [
        st.Page(page, title="Forgalmi térkép", icon="🚗", default=True),
        st.Page(page, title="Forgalmi térkép", icon="🚗", url_path="Forgalmi_Terkep"),
    ],
    position="hidden",
).run()
