import os
import google.generativeai as genai
from dotenv import load_dotenv
import streamlit as st


load_dotenv()
GEMINI_API_KEY = os.getenv("API_KEY")


genai.configure(api_key=GEMINI_API_KEY)


st.title("Real-time Translator with Tone")


generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}


model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
)


chat_session = model.start_chat(
    history=[]
)


input_text = st.text_area("Enter the text to translate", "")
tone = st.selectbox("Select the tone", ["Formal", "Casual", "Happy", "Sad", "Neutral"])
target_language = st.text_area("Enter the language you want to change","")


if st.button("Translate"):
    if input_text:
        prompt = f"Translate the following text to {target_language} language with a {tone} tone:\n\n{input_text}"
        response = chat_session.send_message(prompt)
        st.write("### Translated Text")
        st.write(response.text)
    else:
        st.write("Please enter some text to translate.")
