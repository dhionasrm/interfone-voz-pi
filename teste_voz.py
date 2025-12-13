import sounddevice as sd
import vosk
import json
import queue
import time
import sys
import socket
import sqlite3
import os       # <--- Para mandar comandos ao sistema
import platform # <--- Para saber se é Windows ou Linux

# --- Configurações ---
MODEL_PATH = "model-pt"
TARGET_WORD_1 = "abrir"
TARGET_WORD_2 = "portão"
DEVICE = None
SAMPLE_RATE = 16000
BLOCK_SIZE = 8000
CHECK_INTERVAL = 2
DB_NAME = "interfone.db"

# --- Fila para comunicação ---
q = queue.Queue()

def audio_callback(indata, frames, time, status):
    """Callback do microfone."""
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

def check_internet():
    """Tenta conectar ao Google DNS."""
    # return False  # <--- Descomente para testar OFFLINE forçado
    try:
        socket.setdefaulttimeout(1.5)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except socket.error:
        return False

# --- NOVA FUNÇÃO DE FALA (ROBUSTA) ---
def falar_feedback(mensagem):
    """
    Usa o sistema operacional para falar, evitando conflito com o microfone.
    """
    print(f"🗣️  Dudis diz: '{mensagem}'")
    
    sistema = platform.system()

    if sistema == "Windows":
        # Comando PowerShell para falar no Windows (Nativo)
        # O parâmetro -Command executa um script C# inline para usar a voz do sistema
        comando = f'PowerShell -Command "Add-Type –AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\'{mensagem}\');"'
        os.system(comando)
    
    elif sistema == "Linux":
        # Comando espeak para Linux/Raspberry Pi
        # -v pt (voz português)
        # -s 160 (velocidade)
        comando = f'espeak -v pt-br -s 140 "{mensagem}" --stdout | aplay'
        os.system(comando)

def toggle_master_relay(ativo):
    """Simula a troca do relé mestre."""
    if ativo:
        print("\n🔴 [HARDWARE] RELÉ MESTRE ATIVADO: Desviando áudio para o Raspberry Pi.")
        falar_feedback("Atenção. Sistema de voz de emergência ativado.")
    else:
        print("\n🟢 [HARDWARE] RELÉ MESTRE DESLIGADO: Devolvendo áudio para o Interfone IP.")
        falar_feedback("Conexão restabelecida.")

def open_door():
    """Simula abrir o portão."""
    print("\n" + "="*30)
    print("  >>> COMANDO: ABRIR PORTÃO <<<")
    falar_feedback("Portão liberado. Pode entrar.")
    print("="*30 + "\n")

def buscar_ramal(frase_ouvida):
    """Consulta o banco de dados."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT apartamento, nome_fala FROM ramais")
        todos_ramais = cursor.fetchall()
        conn.close()
        
        for ramal in todos_ramais:
            numero_apto = ramal[0]
            fala_banco = ramal[1].lower()
            
            if fala_banco in frase_ouvida.lower():
                return numero_apto, fala_banco
                
        return None, None
    except Exception as e:
        print(f"Erro banco: {e}")
        return None, None

def main():
    try:
        if not vosk.Model(MODEL_PATH):
            print(f"Erro: Modelo não encontrado em '{MODEL_PATH}'.")
            sys.exit(1)
        
        print("Carregando modelo de voz...")
        model = vosk.Model(MODEL_PATH)
        
        sistema_em_contingencia = False
        last_check = 0
        
        print("Iniciando microfone...")
        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE, 
                               device=DEVICE, dtype='int16',
                               channels=1, callback=audio_callback):

            # Vocabulário livre (sem lista restritiva)
            recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)
            
            print("\n📡 SISTEMA INICIADO. Monitorando conectividade...")

            while True:
                current_time = time.time()

                # --- MONITORAMENTO ---
                if (current_time - last_check > CHECK_INTERVAL) or sistema_em_contingencia:
                    tem_internet = check_internet()
                    last_check = current_time

                    if not tem_internet and not sistema_em_contingencia:
                        print("\n⚠️ ALERTA: Queda de internet!")
                        sistema_em_contingencia = True
                        toggle_master_relay(True)
                        with q.mutex: q.queue.clear() 
                    
                    elif tem_internet and sistema_em_contingencia:
                        print("\n✅ Internet voltou.")
                        sistema_em_contingencia = False
                        toggle_master_relay(False)

                # --- PROCESSAMENTO ---
                if not sistema_em_contingencia:
                    try:
                        while True: q.get_nowait()
                    except queue.Empty: pass
                    time.sleep(0.1)
                    continue

                try:
                    data = q.get(timeout=1)
                except queue.Empty:
                    continue

                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get('text', '')
                    
                    if text:
                        print(f"🎤 Ouvido: '{text}'")
                        
                        # 1. Abrir Portão
                        if TARGET_WORD_1 in text and TARGET_WORD_2 in text:
                            open_door()
                        
                        # 2. Chamar Ramal
                        else:
                            apto, nome_falado = buscar_ramal(text)
                            if apto:
                                print(f"📞 Chamando: {apto}")
                                # O sistema confirma o que entendeu
                                falar_feedback(f"Chamando apartamento {nome_falado}, aguarde.")
                            else:
                                pass 

    except KeyboardInterrupt:
        print("\n👋 Encerrando.")
        sys.exit(0)
    except Exception as e:
        print(f"Erro fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()