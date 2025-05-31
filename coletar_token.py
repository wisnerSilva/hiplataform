import os
import uuid
import requests
from datetime import datetime, timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from supabase import create_client, Client

EMAIL = os.getenv("EMAIL_HIPLAT")
SENHA = os.getenv("SENHA_HIPLAT")
RELATORIO_URL = os.getenv("RELATORIO_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_KEY")
TABLE_NAME = "public.hiplatform_tokens"
BUCKET_NAME = "hiplatform_tokens"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"
}

def iniciar_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--headless')
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

def fazer_login(driver, email, senha, timeout=20):
    wait = WebDriverWait(driver, timeout)
    driver.get("https://horus.hiplatform.com/")
    try:
        btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@value='Continuar']")))
        btn.click()
    except:
        pass
    inp = wait.until(EC.presence_of_element_located((By.ID, "login_login")))
    inp.clear()
    inp.send_keys(email)
    pwd = wait.until(EC.presence_of_element_located((By.ID, "login_password")))
    pwd.clear()
    pwd.send_keys(senha)
    ok = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@value='Entrar' and not(@disabled)]")))
    ok.click()
    wait.until(EC.url_contains("/products"))

def coletar_token(email, senha, url, max_wait=60):
    driver = iniciar_driver()
    try:
        fazer_login(driver, email, senha)
        driver.get(url)
        wait = WebDriverWait(driver, max_wait)
        token = wait.until(lambda d: d.execute_script(
            "return window.localStorage.getItem('dt.admin.token');"
        ))
        return token
    except Exception as e:
        print("Erro ao coletar token:", e)
        return None
    finally:
        driver.quit()

def criar_bucket_se_nao_existir():
    url = f"{SUPABASE_URL}/storage/v1/bucket"
    body = {"name": BUCKET_NAME, "public": False}
    response = requests.post(url, headers=headers, json=body)
    if response.status_code in [200, 400] and "already exists" in response.text:
        return
    elif response.status_code != 200:
        print("Erro ao criar bucket:", response.text)

def salvar_token_no_bucket(token):
    criar_bucket_se_nao_existir()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    file_name = f"{timestamp}.txt"
    upload_url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{file_name}"
    upload_headers = headers.copy()
    upload_headers["Content-Type"] = "text/plain"
    response = requests.post(upload_url, headers=upload_headers, data=token.encode("utf-8"))
    if response.status_code not in [200, 201]:
        print("Erro ao salvar token:", response.text)

def salvar_token_na_tabela(token: str):
    now = datetime.now(timezone.utc).isoformat()
    dados = {"token": token, "created_at": now}
    response = supabase.table(TABLE_NAME).insert(dados).execute()
    if hasattr(response, 'error') and response.error:
        print("Erro ao salvar na tabela:", response.error.message)

if __name__ == "__main__":
    token = coletar_token(EMAIL, SENHA, RELATORIO_URL)
    if token:
        salvar_token_no_bucket(token)
        salvar_token_na_tabela(token)
    else:
        print("Token não coletado.")
