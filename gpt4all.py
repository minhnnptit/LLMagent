from transformers import GPT2LMHeadModel, GPT2Tokenizer
import os
from time import time
from .file_io import save_file

def gpt(system_msg: str, user_msg: str, model_name="openai-community/gpt2", log=True):
    # Load GPT-2 model and tokenizer
    tokenizer = GPT2Tokenizer.from_pretrained(model_name)
    model = GPT2LMHeadModel.from_pretrained(model_name)
    
    # Prepare the prompt
    prompt = f"{system_msg}\n{user_msg}"
    
    # Encode the input
    input_ids = tokenizer.encode(prompt, return_tensors="pt")

    try:
        # Generate text
        output = model.generate(input_ids, max_length=100, num_return_sequences=1)
        response = tokenizer.decode(output[0], skip_special_tokens=True)
        
        text = response.strip()
        filename = '%s_gpt.txt' % time()

        if not os.path.exists('gpt_logs'):
            os.makedirs('gpt_logs')

        # Log the response if needed
        if log:
            save_file('gpt_logs/%s' % filename, system_msg + '\n\n==========\n\n' + user_msg + '\n\n==========\n\n' + text)
        
        return text
    except Exception as e:
        return f"GPT-2 error: {str(e)}"
