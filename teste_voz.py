import sounddevice as sd
import vosk
import json
import queue
import time
import sys

# --- Configurações ---
MODEL_PATH = "model-pt"        
TARGET_WORD_1 = "abrir"        
TARGET_WORD_2 = "portão"        
DEVICE = None                   
SAMPLE_RATE = 16000             
BLOCK_SIZE = 8000               

# --- Fila para comunicação entre o áudio e o processador ---
q = queue.Queue()

def audio_callback(indata, frames, time, status):
    """
    Esta função é chamada pelo 'sounddevice' para cada bloco de áudio.
    Ela roda em uma thread separada.
    """
    if status:
        print(status, file=sys.stderr)
    # Adiciona os dados de áudio na fila
    q.put(bytes(indata))

def open_door():
    """
    Função 'mock' (simulada).
    No Raspberry Pi, esta função ativaria o relé.
    """
    print("\n" + "="*30)
    print("  >>> COMANDO RECONHECIDO! <<<")
    print("  >>> SIMULANDO: Ativando o relé...")
    time.sleep(1) # Simula o tempo que o botão ficaria pressionado
    print("  >>> SIMULANDO: Desativando o relé.")
    print("="*30 + "\n")

# --- Função Principal ---
def main():
    try:
        # 1. Verifica se o modelo existe
        if not vosk.Model(MODEL_PATH):
            print(f"Erro: Modelo de voz não encontrado em '{MODEL_PATH}'.")
            print("Baixe o modelo em: https://alphacephei.com/vosk/models")
            sys.exit(1)
        
        # 2. Carrega o modelo
        model = vosk.Model(MODEL_PATH)
        
        # 3. Abre o stream de áudio (microfone)
        print("Iniciando stream de áudio...")
        with sd.RawInputStream(samplerate=SAMPLE_RATE, 
                               blocksize=BLOCK_SIZE, 
                               device=DEVICE, 
                               dtype='int16',
                               channels=1, 
                               callback=audio_callback):

            # 4. Inicializa o reconhecedor Vosk
            # As palavras-chave são passadas como 'hints' para melhorar a precisão
            recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE, 
                                              f'["{TARGET_WORD_1}", "{TARGET_WORD_2}", "[unk]"]')
            
            print("\n🚀 Sistema pronto. Diga 'abrir portão'...\n")

            # 5. Loop principal de processamento
            while True:
                # Pega dados de áudio da fila (bloqueia até ter dados)
                data = q.get()
                
                # Alimenta o reconhecedor com os dados de áudio
                if recognizer.AcceptWaveform(data):
                    # Se o reconhecedor tiver um resultado final (frase completa)
                    result_text = recognizer.Result()
                    
                    # O resultado é um JSON em formato string, precisamos converter
                    result_json = json.loads(result_text)
                    text = result_json.get('text', '')
                    
                    if text:
                        print(f"Ouvido: '{text}'")
                        
                        # 6. VERIFICAÇÃO DO COMANDO
                        if TARGET_WORD_1 in text and TARGET_WORD_2 in text:
                            open_door() # Chama nossa função simulada!
                    
                # else:
                    # Se quiser ver o processamento parcial (palavra por palavra)
                    # partial_json = json.loads(recognizer.PartialResult())
                    # print(f"Parcial: {partial_json.get('partial', '')}")
                    pass

    except KeyboardInterrupt:
        print("\n👋 Encerrando o programa.")
        sys.exit(0)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()