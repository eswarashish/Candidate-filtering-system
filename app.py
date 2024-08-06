from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import pandas as pd
import fitz
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from typing import List,Tuple,TypedDict, Annotated, Sequence
import streamlit as st
import numpy as np
import tiktoken
import tkinter as tk
from tkinter import filedialog, simpledialog
import re
from langgraph.graph import StateGraph, state
import operator
from resume_prompt import resume_prompt
from jd_prompt import jd_prompt
from grading_prompt import grading_prompt
from timings import timings
from emails import email

df = {
   "Name":[],
   "Email id":[],
    "Contact No.":[],
     "Resume_Summary": [],
     "Fitment":{
        "Criteria": [],
        "Score": [],
        "Weightage": [],
        "Reasoning": []
    },
     "Analysis":{
        "Strengths": [],
        "Weaknesses": [],
        "Risk Areas": [],
     },
    "Score":[],
    "Candidate Summary":[],
    "Questions to ask": [],
    "Timing/Schedule": [],
    "Email_Draft":[],
     
}

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HELICONE_API_KEY=os.getenv("HELICONE_API_KEY")
SysPromptDefault = "You are now in the role of an expert AI."
pdf_list  = []
jd_2 = None
phase_2= False

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]

def response(message: object, model: object = "llama3-8b-8192", SysPrompt: object = SysPromptDefault, temperature: object = 0.2) -> object:
    """

    :rtype: object
    """
    client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://gateway.hconeai.com/openai/v1",
        default_headers={
            "Helicone-Auth": f"Bearer {HELICONE_API_KEY}",
            "Helicone-Target-Url": "https://api.groq.com"
        }
    )

    messages = [{"role": "system", "content": SysPrompt}, {"role": "user", "content": message}]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        frequency_penalty=0.2,
    )
    return response.choices[0].message.content

def extract_content(pdf_content: bytes) -> List[str]:
    """
    Takes PDF (bytes) and returns a list of strings containing text from each page.
    """
    pdf_doc = fitz.open(stream=pdf_content, filetype="pdf")

    pages_content = []
    for page_number in range(pdf_doc.page_count):
        # Extracting text content
        page = pdf_doc.load_page(page_number)
        text_content = page.get_text("text").replace("\n", "\t")
        pages_content.append(text_content)

    pdf_doc.close()
    return pages_content

  

def function_info(x):
  
     pdf_list = x["messages"]
     model = "llama3-70b-8192"
     batch_size = 3
     all_responses_json = []
     for i in range(0, len(pdf_list), batch_size):
         batch = pdf_list[i:i + batch_size]
         print(f"Processing batch from index {i} to {i + batch_size} ")
         context = "Next file\n\n".join([f"Resume File:\n\n{pdf}\n\n" for pdf in batch])
        
         message = f"RESUMES LIST \n\n{context}\n\n"
         response_json = extract_json(response(message=message, model=model, SysPrompt=resume_prompt))
         all_responses_json.append(response_json)
     
     for response_json in all_responses_json:
      for key,value in response_json.items():
        print(key)
        df["Name"].append(value["name"])
        df["Email id"].append(value["email_id"])
        df["Contact No."].append(value["contact_no"])
        df["Resume_Summary"].append(value["resume_summary"])
     
     x["messages"][-1]= all_responses_json

def classify_jd(job_description):
    model = "llama3-70b-8192"
    message = f"JOB_DESCRIPTION\n\n{job_description}\n\n"
    response_str = response(message=message, model=model, SysPrompt=jd_prompt, temperature=0)
    json_part = extract_json(response_str)
    return json_part

def function_fitment(x):
    global df
    global jd_2
    jd_2=classify_jd(jd_2)
    resumes_json={}
    for json_nest in x["messages"][-1]:
     resumes_json.update(json_nest)
        
    batch_size = 3
    resume_keys = list(resumes_json.keys())
    model = "llama3-70b-8192"
    all_responses_json = []
    for i in range(0, len(resume_keys), batch_size):
     batch_keys = resume_keys[i:i + batch_size]
     print(f"Processing batch from index {i} to {i + batch_size} (keys: {batch_keys})")
    
     context = f"\n\nNEXT RESUME:\n\n".join(f"RESUME:{json.dumps(resumes_json[key], indent=4)}" for key in batch_keys)
    
     message = f"\n\nJOB_DESCRIPTION:\n\n{json.dumps(jd_2, indent=4)}\n\nRESUMES LIST:\n\n{context}"
    
     output_str = response(message=message, model=model, SysPrompt=grading_prompt, temperature=0)
     output = extract_json(output_str)
     print(f"Extracted JSON: {output}")
     all_responses_json.append(output)
    for response_json in all_responses_json:
       
        for key,value in response_json.items():
          u = []
          v = []
          w = []
          z = []
          for section, values in value.items():
           if section!="overall_score" and section!="summary" and section!="strengths" and section!="weaknesses" and section!="risk_areas" and section!="questions": 
                
                u.append(section)
                
                v.append(values["score"])
                
                w.append(values["weightage"])
                
                z.append(values["reasoning"])
                
           if section=='strenghts':
               df["Analysis"]["Strengths"].append(value["strengths"])
           if section=='weaknesses':
               df["Analysis"]["Weaknesses"].append(value["weaknesses"])
           if section=='risk_areas':
               df["Analysis"]["Risk Areas"].append(value["risk_areas"])
          df["Fitment"]["Criteria"].append(u)
          df["Fitment"]["Score"].append(v)
          df["Fitment"]["Weightage"].append(w)
          df["Fitment"]["Reasoning"].append(z)
          df["Score"].append(value["overall_score"])
          df["Questions to ask"].append(value["questions"])
          df["Candidate Summary"].append(value["summary"])
    df = flatten_dict(df)
    
    

def flatten_dict(data):
     length = len(data['Name'])
    
     flat_data = []
     for i in range(length):
         entry = {
            'Name': data['Name'][i] if i < len(data['Name']) else None,
            'Email id': data['Email id'][i] if i < len(data['Email id']) else None,
            'Contact No.': data['Contact No.'][i] if i < len(data['Contact No.']) else None,
            'Resume_Summary': data['Resume_Summary'][i] if i < len(data['Resume_Summary']) else None,
            'Score': data['Score'][i] if i < len(data['Score']) else None,
            'Candidate Summary': data['Candidate Summary'][i] if i < len(data['Candidate Summary']) else None,
            'Questions to ask': data['Questions to ask'][i] if i < len(data['Questions to ask']) else None,
            'Timing/Schedule': None,
            'Email_Draft': None,
        }
    
         # Add nested fields
         for key in ['Criteria', 'Score', 'Weightage', 'Reasoning']:
             if key in data['Fitment']:
              if key in ['Score', 'Weightage', 'Reasoning']:
                 v= 0
                 for a in data["Fitment"]["Criteria"][0]:
                  entry[f"Fitment_{a}_{key}"]=data["Fitment"][key][i][v] if i < len(data["Fitment"][key]) else None
                  v += 1
                 
                 

             
             else:
               entry[f'Fitment_{key}'] = None
        
         for key in ['Strengths', 'Weaknesses', 'Risk Areas']:
              entry[f'Analysis_{key}'] = data['Analysis'][key][i] if i < len(data['Analysis'][key]) else None
        
         flat_data.append(entry)
    
     return pd.DataFrame(flat_data)          

def extract_json(response_str):
    """Extract the JSON part from the response string and handle comments."""
    response_str = re.sub(r'//.*?\n|/\*.*?\*/', '', response_str, flags=re.DOTALL)
    response_str = re.sub(r'[\x00-\x1F\x7F]', '', response_str)
    match = re.search(r"\{.*}", response_str, re.DOTALL)
    if match:
        json_part = match.group()
        try:
            parsed_json = json.loads(json_part)
            return parsed_json
        except json.JSONDecodeError as e:
            print("Invalid JSON detected. Error:", e)
            print("JSON part:", json_part)
    else:
        print("No JSON part found in the response string.")
        return None
st.title('Resume Shortlister')



def functions_sort_timings(x):
    global df
    df = df.sort_values(by="Score", ascending=False).head(5)
    input_user = x["messages"][-1]
    context = f"USER_INPUT:{input_user}\n\nCANDIDATES DETAILS:\n\n"
    for index, row in df.iterrows():
     context += f"Name: {row['Name']}\nResume Summary: {row['Resume_Summary']}\n\n"
    ans = response(message=context,SysPrompt=timings)
    response_json = extract_json(ans)
    df["Timing/Schedule"] = df["Name"].map(response_json)

    

    

def function_email(x):
    g = x["messages"][-1]
    print(g)
    global jd_2
    global df
    job_role = jd_2["position_role"]
    job_req = jd_2["requirements"]
    context = f"JOB DETAILS:{job_role}\nJOB REQUIREMENTS:{job_req}\n\n"
    for index, row in df.iterrows():
     context += f"Name: {row['Name']}\nResume Summary: {row['Resume_Summary']}\n Timinings: {row['Timing/Schedule']}\n\n"
    ans = response(message=context,SysPrompt=email)
    st.write(ans)
    response_json = extract_json(ans)
    df["Email_Draft"] = df["Name"].map(response_json)
    

workflow = StateGraph(AgentState)
workflow.add_node("start",function_info)
workflow.add_node("end",function_fitment)
workflow.add_edge("start","end")

workflow.set_entry_point("start")
workflow.set_finish_point("end")


app = workflow.compile()
approach =  StateGraph(AgentState)
approach.add_node("timings_sort",functions_sort_timings)
approach.add_node("emails_draft",function_email)
approach.add_edge("timings_sort","emails_draft")
approach.set_entry_point("timings_sort")
approach.set_finish_point("emails_draft")
app_1 = approach.compile()



x = {}
pdf = st.file_uploader("Choose a CSV file", accept_multiple_files=True)
jd = st.file_uploader("Choose a jd",  accept_multiple_files=False)
f = st.text_input("Enter the timings for the candidates that would be sorted")
if pdf and jd:
 if st.button("Submit"):
    for i in range(len(pdf)):
        pdf_content = pdf[i].read()
        pdf_list.append(extract_content(pdf_content))   
    jd_1 = jd.read()
    jd_2 = extract_content(jd_1)
    a = app.invoke({"messages":pdf_list})
    st.dataframe(df)
    phase_2 = True
    if phase_2==True:
     r = app_1.invoke({"messages":[HumanMessage(f)]})
     st.dataframe(df)
else: 
         st.write("Make sure you enter both the jd and resumes in pdf format")
