# code.py

import time
import board
import busio
import displayio # <<--- AGGIUNGI QUESTO IMPORT
from i2cdisplaybus import I2CDisplayBus
import adafruit_displayio_ssd1306
import random

# Importa la classe e le costanti necessarie dalla libreria
from robo_eyes_cp import RoboEyesCP 
# Se usi le costanti di stato direttamente in code.py, importale anche:
from robo_eyes_cp import CP_STATE_DEFAULT, CP_STATE_HAPPY, CP_STATE_SLEEPY, CP_STATE_SURPRISED
# Oppure accedi tramite la classe se definite come attributi di classe: RoboEyesCP.STATE_DEFAULT

# Se vuoi attivare il debug della libreria da code.py (opzionale)
# import robo_eyes_cp # Importa il modulo
# robo_eyes_cp.LIB_DEBUG_MODE = True # Modifica la variabile globale nel modulo

# --- Definizioni Display ---
SCREEN_WIDTH = 128
SCREEN_HEIGHT = 64
OLED_SDA = board.IO3 
OLED_SCL = board.IO4
OLED_ADDR = 0x3C

# --- Setup ---
displayio.release_displays() # Ora displayio è definito
i2c = busio.I2C(OLED_SCL, OLED_SDA) 

display = None 
try:
    display_bus = I2CDisplayBus(i2c, device_address=OLED_ADDR)
    display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=SCREEN_WIDTH, height=SCREEN_HEIGHT)
    print("Display OLED Inizializzato")
except Exception as e:
    print(f"Errore Display: {e}")
    while True: pass

# --- Istanza RoboEyes ---
# Assicurati che il nome della classe qui corrisponda a quello nel file robo_eyes_cp.py
# Se hai chiamato la classe RoboEyesExpressionsCorrected in robo_eyes_cp.py, usa quel nome qui.
# Se l'hai chiamata RoboEyesCP, usa RoboEyesCP.
# Dall'errore precedente, sembra che tu voglia RoboEyesCP.
eyes = RoboEyesCP(display) 

TARGET_FPS_LIB = 8 
# eyes.begin(SCREEN_WIDTH, SCREEN_HEIGHT, TARGET_FPS_LIB) # La libreria C++ ha frame_rate in begin,
                                                       # la nostra versione Python non lo usa in begin
                                                       # ma il loop principale dovrebbe dettare il ritmo
eyes.begin(SCREEN_WIDTH, SCREEN_HEIGHT, TARGET_FPS_LIB) # Passare frame_rate a begin è ok,
                                                        # anche se la classe Python non lo usa per il timing interno
                                                        # ma per inizializzare frame_interval_ms

# Impostazioni opzionali (dovrai implementare questi metodi setter in RoboEyesCP)
# eyes.set_autoblinker(True, 2, 4) 
# eyes.set_idle_mode(True, 1, 3)

# --- Loop Principale ---
print("Avvio loop principale...")
TARGET_FPS_MAIN_LOOP = 8 # Questo FPS controllerà la frequenza di chiamata di eyes.update()
FRAME_INTERVAL_S_MAIN = 1.0 / TARGET_FPS_MAIN_LOOP
last_frame_target_time_main = time.monotonic()

# Lista di stati possibili per il cambio casuale
possible_states = [CP_STATE_DEFAULT, CP_STATE_HAPPY, CP_STATE_SLEEPY, CP_STATE_SURPRISED]


while True:
    # La classe RoboEyesCP.update() esegue la logica e il disegno ad ogni chiamata.
    # Il loop principale qui è responsabile del timing.
    eyes.update() 

    # Non è necessario un cambio di mood casuale qui se la libreria lo gestisce internamente
    # con next_state_eval_time. Se vuoi un controllo esterno, puoi decommentare:
    # current_time_mood = time.monotonic()
    # if current_time_mood - last_mood_change_time > mood_change_interval:
    #     new_mood = random.choice(possible_states)
    #     eyes.set_mood(new_mood) # Dovrai implementare set_mood in RoboEyesCP
    #     last_mood_change_time = current_time_mood
    #     mood_change_interval = random.uniform(5,10)

    # Logica di Frame Rate per il Loop Principale
    current_loop_time = time.monotonic()
    next_target = last_frame_target_time_main + FRAME_INTERVAL_S_MAIN
    sleep_for = next_target - current_loop_time
    if sleep_for > 0:
        time.sleep(sleep_for)
    
    last_frame_target_time_main = next_target
    # Anti-drift per il loop principale
    if current_loop_time - last_frame_target_time_main > FRAME_INTERVAL_S_MAIN * 1.5:
       last_frame_target_time_main = current_loop_time