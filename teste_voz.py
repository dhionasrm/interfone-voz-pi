import sounddevice as sd
import vosk
import json
import queue
import time
import sys
import socket # Necessário para verificar a internet
import sqlite3 # <--- NOVO: Para ler o banco de dados

# --- Configurações ---
MODEL_PATH = "model-pt"         
TARGET_WORD_1 = "abrir"         
TARGET_WORD_2 = "portão"        
DEVICE = None                   
SAMPLE_RATE = 16000             
BLOCK_SIZE = 8000               
CHECK_INTERVAL = 2  # Verifica a internet a cada X segundos
DB_NAME = "interfone.db" # <--- NOVO: Nome do banco de dados

# --- Fila para comunicação ---
q = queue.Queue()

def audio_callback(indata, frames, time, status):
    """Callback do microfone."""
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

def check_internet():
    """
    Tenta conectar ao Google DNS.
    Retorna True se tiver conexão, False se não tiver.
    """
    # --- MODO DE TESTE (TRAPAÇA) ---
    # Se quiser testar o modo OFFLINE sem desligar seu Wi-Fi, 
    # tire o # da linha abaixo:
    # return False  
    # -------------------------------

    try:
        socket.setdefaulttimeout(1.5)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except socket.error:
        return False

def toggle_master_relay(ativo):
    """Simula a troca do relé mestre."""
    if ativo:
        print("\n🔴 [HARDWARE] RELÉ MESTRE ATIVADO: Desviando áudio para o Raspberry Pi.")
    else:
        print("\n🟢 [HARDWARE] RELÉ MESTRE DESLIGADO: Devolvendo áudio para o Interfone IP.")

def open_door():
    """Simula abrir o portão."""
    print("\n" + "="*30)
    print("  >>> COMANDO RECONHECIDO: ABRIR PORTÃO <<<")
    print("  >>> AÇÃO: Ativando relé da fechadura...")
    time.sleep(1) 
    print("  >>> AÇÃO: Fechadura liberada.")
    print("="*30 + "\n")

# --- NOVA FUNÇÃO: BUSCAR NO BANCO DE DADOS ---
def buscar_ramal(frase_ouvida):
    """
    Consulta o banco de dados para ver se a frase dita corresponde a um apartamento.
    Retorna o número do apartamento (ex: "101") ou None.
    """
    try:
        # Conecta ao banco de dados (apenas leitura)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Pega todos os ramais cadastrados
        cursor.execute("SELECT apartamento, nome_fala FROM ramais")
        todos_ramais = cursor.fetchall()
        conn.close()
        
        # Verifica um por um
        for ramal in todos_ramais:
            numero_apto = ramal[0]  # Ex: "101"
            fala_banco = ramal[1].lower() # Ex: "cento e um"
            
            # Se a frase cadastrada estiver dentro do que foi dito
            if fala_banco in frase_ouvida.lower():
                return numero_apto
                
        return None
    except Exception as e:
        print(f"Erro ao consultar banco: {e}")
        return None

# --- Função Principal ---
def main():
    try:
        # 1. Carrega o modelo
        if not vosk.Model(MODEL_PATH):
            print(f"Erro: Modelo não encontrado em '{MODEL_PATH}'.")
            sys.exit(1)
        
        print("Carregando modelo de voz... (isso pode demorar um pouco)")
        model = vosk.Model(MODEL_PATH)
        
        # 2. Configurações iniciais
        sistema_em_contingencia = False
        last_check = 0
        
        # 3. Abre o microfone
        print("Iniciando stream de áudio...")
        with sd.RawInputStream(samplerate=SAMPLE_RATE, 
                               blocksize=BLOCK_SIZE, 
                               device=DEVICE, 
                               dtype='int16',
                               channels=1, 
                               callback=audio_callback):

            # Removemos a lista de palavras restritas
            recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)
            
            print("\n📡 SISTEMA INICIADO. Monitorando conectividade...")

            # 4. Loop Infinito
            while True:
                current_time = time.time()

                # --- MONITORAMENTO DE INTERNET ---
                if (current_time - last_check > CHECK_INTERVAL) or sistema_em_contingencia:
                    tem_internet = check_internet()
                    last_check = current_time

                    if not tem_internet and not sistema_em_contingencia:
                        print("\n⚠️ ALERTA: Queda de internet detectada!")
                        sistema_em_contingencia = True
                        toggle_master_relay(True)
                        with q.mutex: q.queue.clear() 
                    
                    elif tem_internet and sistema_em_contingencia:
                        print("\n✅ RESTABELECIDO: Internet voltou.")
                        sistema_em_contingencia = False
                        toggle_master_relay(False)

                # --- PROCESSAMENTO DE ÁUDIO ---
                
                # Se tem internet, ignora o áudio
                if not sistema_em_contingencia:
                    try:
                        while True: q.get_nowait()
                    except queue.Empty:
                        pass
                    time.sleep(0.1)
                    continue

                # Se SEM INTERNET, processa voz
                try:
                    data = q.get(timeout=1)
                except queue.Empty:
                    continue

                if recognizer.AcceptWaveform(data):
                    result_text = recognizer.Result()
                    result_json = json.loads(result_text)
                    text = result_json.get('text', '')
                    
                    if text:
                        print(f"🎤 Ouvido (OFFLINE): '{text}'")
                        
                        # CASO 1: Comando de abrir portão
                        if TARGET_WORD_1 in text and TARGET_WORD_2 in text:
                            open_door()
                        
                        # CASO 2: Tenta encontrar um ramal no banco de dados
                        else:
                            apto_encontrado = buscar_ramal(text)
                            if apto_encontrado:
                                print(f"\n📞 [AÇÃO] Chamando apartamento: {apto_encontrado}")
                                # Aqui futuramente entra o código para discar/tocar tom
                            else:
                                print("   (Comando não reconhecido)")

    except KeyboardInterrupt:
        print("\n👋 Encerrando o sistema.")
        sys.exit(0)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()