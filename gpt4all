from gpt4all import GPT4All
import os
from time import time
from .file_io import save_file

def gpt(system_msg: str, user_msg: str, model="gpt4all-lora-quantized", log=True):
    # Khởi tạo GPT4ALL với mô hình
    model = GPT4All(model)
    
    prompt = f"{system_msg}\n{user_msg}"
    try:
        # Sinh văn bản từ GPT4ALL
        response = model.generate(prompt)
        
        text = response.strip()
        filename = '%s_gpt.txt' % time()

        if not os.path.exists('gpt_logs'):
            os.makedirs('gpt_logs')
        
        # Ghi lại log nếu cần
        if log:
            save_file('gpt_logs/%s' % filename, system_msg + '\n\n==========\n\n' + user_msg + '\n\n==========\n\n' + text)
        
        return text
    except Exception as e:
        return f"GPT4ALL error: {str(e)}"
