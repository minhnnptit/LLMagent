import openai
import os
from dotenv import load_dotenv
from time import time
from .file_io import save_file

# Tải API key từ file .env
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def gpt(system_msg: str, user_msg: str, model_name="text-davinci-003", log=True):
    # Tạo prompt
    prompt = f"{system_msg}\n{user_msg}"
    
    try:
        # Gọi mô hình GPT-3
        response = openai.Completion.create(
            engine=model_name,
            prompt=prompt,
            max_tokens=200,
            temperature=0.7
        )
        
        # Lấy kết quả từ phản hồi của GPT-3
        text = response.choices[0].text.strip()
        filename = '%s_gpt.txt' % time()

        # Ghi lại log nếu cần
        if log:
            if not os.path.exists('gpt_logs'):
                os.makedirs('gpt_logs')
            save_file(f'gpt_logs/{filename}', f"{system_msg}\n\n==========\n\n{user_msg}\n\n==========\n\n{text}")
        
        return text
    except Exception as e:
        return f"GPT-3 error: {str(e)}"
