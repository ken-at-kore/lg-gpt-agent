import streamlit as st
from streamlit.logger import get_logger
import openai
import pandas as pd
from pandasql import sqldf
import Constants
import json

LOGGER = get_logger(__name__)


def run():

    # Set Streamlit app meta info
    st.set_page_config(
        page_title="LG-GPT with Agency Prototype",
        page_icon="🤖",
    )
    st.title("LG-GPT with Agency Prototype")

    # Load the lG product data
    file_path = 'data/Dishwashers CSV.csv'
    lg_product_data_frame = pd.read_csv(file_path)

    # Set the OpenAI key and model
    openai.api_key = st.secrets["OPENAI_API_KEY"]

    if "openai_model" not in st.session_state:
        st.session_state["openai_model"] = "gpt-4"

    # Initialize UI messages and GPT messages
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": Constants.WELCOME_BOT_MESSAGE}
        ]
        st.session_state["gpt_messages"] = [
            {"role": "system", "content": Constants.SYSTEM_PROMPT},
            {"role": "assistant", "content": Constants.WELCOME_BOT_MESSAGE}
        ]


    # Re-render UI messages
    for message in st.session_state.messages:
        if message["role"] == "user" or message["role"] == "assistant" or message["role"] == "function":
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # Get, store and render user message
    if prompt := st.chat_input("What's up?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state["gpt_messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Prepare assistant response UI
        function_call_response = ""
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            bot_content_response = ""

            # Call OpenAI GPT (Response is streamed)
            for response in openai.ChatCompletion.create(
                model=st.session_state["openai_model"],
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ],
                stream=True,
                temperature=Constants.GPT_TEMPERATURE,
                functions=Constants.GPT_FUNCTIONS
            ):
                # Handle content stream
                if not response.choices[0].delta.get("function_call",""):
                    bot_content_response += response.choices[0].delta.get("content", "")
                    full_response += response.choices[0].delta.get("content", "")
                    message_placeholder.markdown(full_response + "▌")
                
                # Handle function call stream
                else:
                    function_call_response += response.choices[0].delta.function_call.get("arguments", "")
                    if function_call_response == "":
                        full_response += "\n\n"
                    full_response += response.choices[0].delta.function_call.get("arguments", "")
                    message_placeholder.markdown(full_response + "▌")

                message_placeholder.markdown(full_response)
        
        # Handle no function call
        if not function_call_response:
            # Store the bot content
            st.session_state['gpt_messages'].append({"role": "assistant", "content": bot_content_response})
            st.session_state.messages.append({"role": "assistant", "content": bot_content_response})
        
        # Handle function call
        else:
            # Store bot content
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            st.session_state['gpt_messages'].append({"role": "assistant", "content": bot_content_response,
                                                     "function_call": {"name": "query_lg_dishwasher_products", "arguments": function_call_response}})
            
            # Execute query
            query = json.loads(function_call_response).get('sql_query') # Extract query
            try:
                # Apply query to pseudo-DB
                query_result_df = sqldf(query, {"lg_product_data": lg_product_data_frame})

                # Get results
                query_result_text = ""
                if not query_result_df.empty:
                    query_result_df = query_result_df.head(5)
                else:
                    query_result = "Query result: No products found with that criteria"
            except Exception as e:
                query_result_text = str(e) 
        
            # Store query results
            function_result_content = query_result_text if query_result_text != "" else query_result_df
            st.session_state['gpt_messages'].append({"role": "function", "name": "query_lg_dishwasher_products", 
                                                     "content": function_result_content})
            
            # Not sure how I would store the Streamlit message for the function cal result
            # st.session_state.messages.append({"role": "assistant", "content": query_result})

            # Render query results
            with st.chat_message("SQL Result"):
                if query_result_text:
                    st.markdown(query_result_text)
                if query_result_df is not None and not query_result_df.empty:
                    st.markdown("<style>table.dataframe {font-size: 6px;}</style>", unsafe_allow_html=True)
                    st.write(query_result_df)

            # Have the model process the results
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                messages_param = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ]
                for response in openai.ChatCompletion.create(
                    model=st.session_state["openai_model"],
                    messages=messages_param,
                    temperature=Constants.GPT_TEMPERATURE,
                    stream=True
                ):
                    full_response += response.choices[0].delta.get("content", "")
                    message_placeholder.markdown(full_response + "▌")
                message_placeholder.markdown(full_response)
            
            # Store the bot response
            st.session_state['gpt_messages'].append({"role": "assistant", "content": full_response})
            st.session_state.messages.append({"role": "assistant", "content": full_response})


if __name__ == "__main__":
    run()
