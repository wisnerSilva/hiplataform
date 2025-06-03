import os
import uuid
import requests
import pandas as pd
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
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
TABLE_NAME = "hiplatform_tokens"
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
    print("🚀 Iniciando coleta de token via Selenium")
    driver = iniciar_driver()
    try:
        print("➡️ Realizando login")
        fazer_login(driver, email, senha)
        print("➡️ Navegando até o relatório")
        driver.get(url)
        wait = WebDriverWait(driver, max_wait)
        print("🕵️ Tentando extrair token do localStorage")
        token = wait.until(lambda d: d.execute_script(
            "return window.localStorage.getItem('dt.admin.token');"
        ))
        print(f"✅ TOKEN ENCONTRADO: {token}")
        return token
    except Exception as e:
        print("❌ Erro ao coletar token:", str(e))
        return None
    finally:
        driver.quit()
        print("🌐 Navegador fechado")

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
# ============================================
# 🚫🚫🚫 NUNCA ALTERAR O CÓDIGO ACIMA DESTA LINHA 🚫🚫🚫
# Código original do coletor de token - protegido conforme instrução
# ============================================

import os
import uuid
import requests
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
from coletar_token import coletar_token  # função importada do seu script funcional

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
TABLE_HSM = "hsm_mensagens"
TABLE_LOG = "hsm_logs"
EMAIL = os.getenv("EMAIL_HIPLAT")
SENHA = os.getenv("SENHA_HIPLAT")
RELATORIO_URL = os.getenv("RELATORIO_URL")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

API_URL = "https://whatsapp-connect.hiplatform.com/hsmservices/api/Hsm/ExportHsm"
TENANT_ID = "762b7805-51fc-4e84-a614-4eb2b5d4eb16"


def registrar_log(data, mensagem):
    log = {
        "id": str(uuid.uuid4()),
        "data": data.isoformat(),
        "mensagem": mensagem,
        "created_at": datetime.utcnow().isoformat()
    }
    supabase.table(TABLE_LOG).insert(log).execute()

def validar_e_normalizar_colunas(df):
    colunas_existentes = supabase.table(TABLE_HSM).select("*").limit(1).execute().data
    if not colunas_existentes:
        return df
    colunas_db = set(colunas_existentes[0].keys())
    for coluna in df.columns:
        if coluna not in colunas_db:
            try:
                tipo = "text"
                alterar_sql = f"ALTER TABLE {TABLE_HSM} ADD COLUMN \"{coluna}\" {tipo};"
                supabase.rpc("execute_sql", {"sql": alterar_sql}).execute()
                print(f"Nova coluna adicionada: {coluna}")
            except Exception as e:
                print(f"Erro ao adicionar coluna {coluna}: {e}")
    return df

def coletar_e_inserir(token: str, data: datetime):
    start = datetime.combine(data, datetime.min.time())
    end = datetime.combine(data, datetime.max.time())
    payload = {
        "startDate": start.strftime("%Y-%m-%dT%H:%M:%S-03:00"),
        "endDate": end.strftime("%Y-%m-%dT%H:%M:%S-03:00"),
        "origin": 0,
        "senders": [],
        "categories": [],
        "tenantId": TENANT_ID
    }
    headers = {
        "Authorization": f"DT-Fenix-Token {token}",
        "Content-Type": "application/json",
        "Accept": "text/csv"
    }
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.content.decode("utf-16-le")), sep=";")
        if df.empty:
            print(f"Nenhum dado para {data}")
            return
        df = validar_e_normalizar_colunas(df)
        delete_sql = f"DELETE FROM {TABLE_HSM} WHERE DATE(data_hora_disparo) = '{data}';"
        supabase.rpc("execute_sql", {"sql": delete_sql}).execute()
        for _, row in df.iterrows():
            dados = row.to_dict()
            dados['id'] = str(uuid.uuid4())
            dados['created_at'] = datetime.utcnow().isoformat()
            dados['updated_at'] = None
            supabase.table(TABLE_HSM).insert(dados).execute()
        print(f"{len(df)} registros inseridos para {data}")
    except Exception as e:
        print(f"Erro ao inserir dados de {data}: {e}")
        registrar_log(data, str(e))
        raise

if __name__ == "__main__":
    token = coletar_token(EMAIL, SENHA, RELATORIO_URL)
    if not token:
        print("Token inválido. Tentando novamente...")
        token = coletar_token(EMAIL, SENHA, RELATORIO_URL)

    if token:
        print(f"Token adquirido: {token}")
        data_inicio = datetime(2024, 9, 1).date()
        data_fim = datetime.now().date()
        data_atual = data_inicio
        while data_atual <= data_fim:
            try:
                coletar_e_inserir(token, data_atual)
            except Exception:
                print(f"Reobtendo token para {data_atual}...")
                token = coletar_token(EMAIL, SENHA, RELATORIO_URL)
                if token:
                    coletar_e_inserir(token, data_atual)
            data_atual += timedelta(days=1)
        print("Coleta finalizada!")
    else:
        print("Falha ao obter token. Encerrando.")

