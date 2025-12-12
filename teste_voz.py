import sounddevice as sd
import vosk
import json
import queue
import time
import sys
import socket # Necessário para verificar a internet
import sqlite3

# --- Configurações ---
MODEL_PATH = "model-pt"         
TARGET_WORD_1 = "abrir"         
TARGET_WORD_2 = "portão"        
DEVICE = None                   
SAMPLE_RATE = 16000             
BLOCK_SIZE = 8000               
CHECK_INTERVAL = 2  # Verifica a internet a cada X segundos (se estiver online)

# --- Fila para comunicação ---
q = queue.Queue()

def audio_callback(indata, frames, time, status):
    """Callback do microfone."""
    if status:
        print(status, file=sys.stderr)
    q.put(bytes(indata))

def check_internet():
    """
    Tenta conectar ao Google DNS (8.8.8.8) na porta 53.
    Retorna True se tiver conexão, False se não tiver.
    """
    try:
        # Timeout curto (1.5s) para não travar o sistema
        socket.setdefaulttimeout(1.5)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except socket.error:
        return False

def toggle_master_relay(ativo):
    """
    Simula o relé que troca entre o Interfone IP e o Raspberry Pi.
    ativo = True -> Raspberry assume (Internet caiu)
    ativo = False -> Sistema IP assume (Internet ok)
    """
    if ativo:
        print("\n🔴 [HARDWARE] RELÉ MESTRE ATIVADO: Desviando áudio para o Raspberry Pi.")
    else:
        print("\n🟢 [HARDWARE] RELÉ MESTRE DESLIGADO: Devolvendo áudio para o Interfone IP.")

def open_door():
    """Simula a ação final (abrir porta ou chamar ramal)."""
    print("\n" + "="*30)
    print("  >>> COMANDO RECONHECIDO! <<<")
    print("  >>> AÇÃO: Ativando relé da fechadura...")
    time.sleep(1) 
    print("  >>> AÇÃO: Fechadura liberada.")
    print("="*30 + "\n")

# --- Função Principal ---
def main():
    try:
        # 1. Carrega o modelo (Fazemos isso só uma vez no início)
        if not vosk.Model(MODEL_PATH):
            print(f"Erro: Modelo não encontrado em '{MODEL_PATH}'.")
            sys.exit(1)
        
        print("Carregando modelo de voz... (isso pode demorar um pouco)")
        model = vosk.Model(MODEL_PATH)
        
        # 2. Configurações iniciais de estado
        sistema_em_contingencia = False # Começamos assumindo que a internet está OK
        last_check = 0
        
        # 3. Abre o microfone
        print("Iniciando stream de áudio...")
        with sd.RawInputStream(samplerate=SAMPLE_RATE, 
                               blocksize=BLOCK_SIZE, 
                               device=DEVICE, 
                               dtype='int16',
                               channels=1, 
                               callback=audio_callback):

            recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE, 
                                              f'["{TARGET_WORD_1}", "{TARGET_WORD_2}", "[unk]"]')
            
            print("\n📡 SISTEMA INICIADO. Monitorando conectividade...")

            # 4. Loop Infinito
            while True:
                current_time = time.time()

                # --- LÓGICA DE VERIFICAÇÃO DE INTERNET ---
                # Só verifica se passou o intervalo ou se já estamos no modo offline (verificação contínua)
                if (current_time - last_check > CHECK_INTERVAL) or sistema_em_contingencia:
                    tem_internet = check_internet()
                    last_check = current_time

                    # Cenário 1: Internet CAIU, mas o sistema ainda não assumiu
                    if not tem_internet and not sistema_em_contingencia:
                        print("\n⚠️ ALERTA: Queda de internet detectada!")
                        sistema_em_contingencia = True
                        toggle_master_relay(True) # Ativa o relé de desvio
                        # Limpa a fila de áudio antiga para começar a ouvir agora
                        with q.mutex: q.queue.clear() 
                    
                    # Cenário 2: Internet VOLTOU, e o sistema estava assumindo
                    elif tem_internet and sistema_em_contingencia:
                        print("\n✅ RESTABELECIDO: Internet voltou.")
                        sistema_em_contingencia = False
                        toggle_master_relay(False) # Devolve para o interfone original

                # --- LÓGICA DE PROCESSAMENTO ---
                
                # Se tem internet (NÃO está em contingência), ignoramos o áudio
                if not sistema_em_contingencia:
                    # Esvazia a fila sem processar para não acumular memória
                    try:
                        while True: q.get_nowait()
                    except queue.Empty:
                        pass
                    time.sleep(0.1) # Dorme um pouco para economizar CPU
                    continue

                # --- SE ESTIVER EM CONTINGÊNCIA (SEM INTERNET) ---
                # Aqui o código roda igual ao anterior: processa a voz
                try:
                    data = q.get(timeout=1) # Espera áudio chegar
                except queue.Empty:
                    continue

                if recognizer.AcceptWaveform(data):
                    result_text = recognizer.Result()
                    result_json = json.loads(result_text)
                    text = result_json.get('text', '')
                    
                    if text:
                        print(f"🎤 Ouvido (OFFLINE): '{text}'")
                        
                        if TARGET_WORD_1 in text and TARGET_WORD_2 in text:
                            open_door()

    except KeyboardInterrupt:
        print("\n👋 Encerrando o sistema.")
        sys.exit(0)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()