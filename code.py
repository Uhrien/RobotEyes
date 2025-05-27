import time
import board
import busio
import displayio
from i2cdisplaybus import I2CDisplayBus
import adafruit_displayio_ssd1306
import random
import bitmaptools

# --- Costanti ---
BGCOLOR = 0
MAINCOLOR = 1
SCREEN_WIDTH = 128
SCREEN_HEIGHT = 64
EDGE_MARGIN = 5

DEBUG_MODE = False # Flag Unico per il Debug. Imposta a True per stampe.

# --- Definizioni Stati/Espressioni ---
STATE_DEFAULT = "default"
STATE_HAPPY = "happy"
STATE_SURPRISED = "surprised"
STATE_SLEEPY = "sleepy"

ACTION_BLINK = "blinking"

class RoboEyesExpressionsCorrected(object): # Nome corretto come da errore
    def __init__(self, display_instance):
        self.display = display_instance
        self.screen_width = SCREEN_WIDTH
        self.screen_height = SCREEN_HEIGHT

        self.screen_palette = displayio.Palette(2); self.screen_palette[BGCOLOR]=0; self.screen_palette[MAINCOLOR]=0xFFFFFF
        self.screen_bitmap = displayio.Bitmap(SCREEN_WIDTH, SCREEN_HEIGHT, 2)
        self.screen_tile_grid = displayio.TileGrid(self.screen_bitmap, pixel_shader=self.screen_palette)
        self.main_group = displayio.Group(); self.main_group.append(self.screen_tile_grid)
        self.display.root_group = self.main_group

        self.base_eye_width = 36
        self.base_eye_height = 36
        self.eye_border_radius = 8

        # --- Sprite Occhi ---
        self.eye_sprite_open = self._create_round_rect_sprite( # DEFINITO QUI
            self.base_eye_width, self.base_eye_height, self.eye_border_radius, MAINCOLOR, BGCOLOR)
        
        blink_h1 = max(1, int(self.base_eye_height * 0.60)) 
        blink_h2 = max(1, int(self.base_eye_height * 0.25)) 
        blink_h_line = max(1, 6) # Linea più spessa

        self.sprite_eye_happy_form = self._create_round_rect_sprite(
            self.base_eye_width, blink_h1, self.eye_border_radius // 2 if self.eye_border_radius > 1 else 1, 
            MAINCOLOR, BGCOLOR)
        self.sprite_eye_mostly_closed = self._create_round_rect_sprite( # Per SLEEPY
            self.base_eye_width, blink_h2, self.eye_border_radius // 4 if self.eye_border_radius > 3 else 1, 
            MAINCOLOR, BGCOLOR)
        self.sprite_eye_line = self._create_round_rect_sprite( # Per SLEEPY o blink
            self.base_eye_width, blink_h_line, 2 if blink_h_line > 3 else 1, MAINCOLOR, BGCOLOR)
        
        self.eye_sprite_surprised_open = self.eye_sprite_open # Per ora uguale a open


        self.blink_animation_sprites = [
            self.eye_sprite_open, 
            self.sprite_eye_happy_form, # Usiamo happy_form come intermedio (era blink_frame1)
            self.sprite_eye_line, 
            self.sprite_eye_happy_form, # Usiamo happy_form come intermedio
            self.eye_sprite_open,
        ]
        self.blink_anim_frame_count = len(self.blink_animation_sprites)

        # --- Stato Occhi (Posizione, Target) ---
        self.eyeL_x, self.eyeL_y = 0.0, 0.0; self.eyeR_x, self.eyeR_y = 0.0, 0.0
        self.eye_target_L_x, self.eye_target_L_y = 0.0, 0.0; self.eye_target_R_x, self.eye_target_R_y = 0.0, 0.0
        self.eye_default_spacing = 10
        _total_default_width = self.base_eye_width * 2 + self.eye_default_spacing
        self.eye_default_L_x = float((SCREEN_WIDTH - _total_default_width) // 2)
        self.eye_default_L_y = float((SCREEN_HEIGHT - self.base_eye_height) // 2)
        self.eye_default_R_x = self.eye_default_L_x + self.base_eye_width + self.eye_default_spacing
        self.eye_default_R_y = self.eye_default_L_y
        self.eye_target_L_x, self.eye_target_L_y = self.eye_default_L_x, self.eye_default_L_y
        self.eye_target_R_x, self.eye_target_R_y = self.eye_default_R_x, self.eye_default_R_y
        self.eyeL_x, self.eyeL_y = self.eye_default_L_x, self.eye_default_L_y
        self.eyeR_x, self.eyeR_y = self.eye_default_R_x, self.eye_default_R_y

        # --- Sistema di Stati/Azioni ---
        self.current_state = STATE_DEFAULT
        self.state_start_time = 0.0
        self.state_duration = 0.0
        self.expression_eval_interval_s = 5.0 
        self.expression_eval_interval_variation_s = 5.0
        self.next_state_eval_time = time.monotonic() + self._get_random_delay(
            self.expression_eval_interval_s, self.expression_eval_interval_variation_s) 

        self.is_performing_blink_anim = False 
        self.blink_anim_current_frame = 0 # Rinominato da action_anim_frame per chiarezza
        self.blink_anim_next_frame_time = 0.0 # Rinominato da action_anim_next_frame_time
        self.blink_frame_duration = 0.08

        # --- Movimento Idle ---
        self.idle_active = True
        self.idle_interval_s = 2.0 
        self.idle_interval_variation_s = 2.0
        self.idle_next_time = time.monotonic() + self._get_random_delay(self.idle_interval_s, self.idle_interval_variation_s)
        
        self._last_debug_print_time = 0.0
        if DEBUG_MODE: print(f"{self.__class__.__name__} Inizializzato")


    def _get_random_delay(self, base, variation):
        return base + random.uniform(0, variation)

    def _constrain(self, val, min_val, max_val):
        actual_max = max(min_val, max_val)
        return max(min_val, min(val, actual_max))

    def _create_rect_sprite(self, width, height, color_index_fill, palette_to_use):
        sprite = displayio.Bitmap(int(width), int(height), len(palette_to_use))
        sprite.fill(color_index_fill)
        return sprite

    def _create_round_rect_sprite(self, width, height, radius, color_index_draw, color_index_bg, palette_to_use=None):
        _palette = palette_to_use if palette_to_use else self.screen_palette
        _width_int, _height_int, _radius_int = int(width), int(height), int(radius)
        _radius_int = min(_radius_int, _width_int // 2, _height_int // 2)
        if _radius_int < 0: _radius_int = 0
        sprite = displayio.Bitmap(_width_int, _height_int, len(_palette))
        sprite.fill(color_index_bg)
        if _width_int <= 0 or _height_int <=0: return sprite
        if _width_int > 2 * _radius_int and _height_int > 0:
             bitmaptools.fill_region(sprite, _radius_int, 0, _width_int - _radius_int, _height_int, color_index_draw)
        if _height_int > 2 * _radius_int and _width_int > 0:
             bitmaptools.fill_region(sprite, 0, _radius_int, _width_int, _height_int - _radius_int, color_index_draw)
        def _draw_filled_circle_on_sprite(s_bitmap, cx, cy, r, color_idx):
            for x_offset in range(-r, r + 1):
                for y_offset in range(-r, r + 1):
                    if x_offset*x_offset + y_offset*y_offset <= r*r:
                        px, py = cx + x_offset, cy + y_offset
                        if 0 <= px < s_bitmap.width and 0 <= py < s_bitmap.height:
                            s_bitmap[px, py] = color_idx
        if _radius_int > 0 :
            _draw_filled_circle_on_sprite(sprite, _radius_int, _radius_int, _radius_int, color_index_draw)
            _draw_filled_circle_on_sprite(sprite, _width_int - _radius_int - 1, _radius_int, _radius_int, color_index_draw)
            _draw_filled_circle_on_sprite(sprite, _radius_int, _height_int - _radius_int - 1, _radius_int, color_index_draw)
            _draw_filled_circle_on_sprite(sprite, _width_int - _radius_int - 1, _height_int - _radius_int - 1, _radius_int, color_index_draw)
        elif _width_int > 0 and _height_int > 0 : 
            sprite.fill(color_index_draw)
        return sprite

    def _blit_sprite(self, source_bitmap, dest_x, dest_y, skip_index_in_source_palette=None, debug_name=""): # debug_name non usato attivamente
        _dest_x_int = round(dest_x); _dest_y_int = round(dest_y)
        if _dest_x_int + source_bitmap.width <= 0: return
        if _dest_x_int >= self.screen_width: return
        if _dest_y_int + source_bitmap.height <= 0: return
        if _dest_y_int >= self.screen_height: return
        if _dest_y_int < 0 : return 
        try: bitmaptools.blit(self.screen_bitmap, source_bitmap, _dest_x_int, _dest_y_int, skip_source_index=skip_index_in_source_palette)
        except Exception as e:
            if DEBUG_MODE: print(f"*** Errore Blit {debug_name} xy=({_dest_x_int},{_dest_y_int}): {e}")

    def _handle_blink_animation(self, current_time): # Rinominato da _handle_active_action
        if not self.is_performing_blink_anim: return

        if current_time >= self.blink_anim_next_frame_time:
            self.blink_anim_current_frame += 1
            if self.blink_anim_current_frame >= self.blink_anim_frame_count:
                self.is_performing_blink_anim = False
                self.blink_anim_current_frame = 0 # Resetta per la prossima volta (o all'ultimo frame "aperto")
                # Non resettare current_state qui, _update_state_machine lo farà se necessario
            else:
                self.blink_anim_next_frame_time = current_time + self.blink_frame_duration
    
    def _trigger_blink(self, current_time): # Rinominato da _trigger_action
        if not self.is_performing_blink_anim: 
            self.is_performing_blink_anim = True
            # self.current_state = STATE_DEFAULT # Il blink non dovrebbe cambiare lo stato emotivo di base
            self.blink_anim_current_frame = 0 
            self.blink_anim_next_frame_time = current_time 
            if DEBUG_MODE: print(f"ACTION: Blink Start @{current_time:.2f}")

    def _update_state_machine(self, current_time):
        if self.current_state != STATE_DEFAULT and \
           not self.is_performing_blink_anim and \
           current_time >= self.state_start_time + self.state_duration:
            self.current_state = STATE_DEFAULT
            if DEBUG_MODE: print(f"STATE -> DEFAULT @{current_time:.2f}")

        if self.current_state == STATE_DEFAULT and \
           not self.is_performing_blink_anim and \
           current_time >= self.next_state_eval_time:
            
            action_eff_duration = 0.0 
            rand_val = random.random()
            chosen_state = None

            if rand_val < 0.35: 
                self._trigger_blink(current_time)
                action_eff_duration = (self.blink_anim_frame_count -1) * self.blink_frame_duration
            elif rand_val < 0.60: 
                chosen_state = STATE_HAPPY
                self.state_duration = random.uniform(2.0, 4.0)
            elif rand_val < 0.80: 
                chosen_state = STATE_SURPRISED
                self.state_duration = random.uniform(1.0, 2.5)
            else: 
                chosen_state = STATE_SLEEPY
                self.state_duration = random.uniform(3.0, 6.0)
            
            if chosen_state:
                self.current_state = chosen_state
                self.state_start_time = current_time
                action_eff_duration = self.state_duration
                if DEBUG_MODE: print(f"STATE -> {self.current_state} for {self.state_duration:.1f}s")
            
            self.next_state_eval_time = current_time + action_eff_duration + \
                self._get_random_delay(self.expression_eval_interval_s, self.expression_eval_interval_variation_s)


    def update(self):
        current_time = time.monotonic()
        tween_factor = 0.25

        self._update_state_machine(current_time)
        if self.is_performing_blink_anim:
            self._handle_blink_animation(current_time)
        
        can_idle_move = not self.is_performing_blink_anim
        if self.current_state == STATE_SURPRISED: can_idle_move = False
        if self.current_state == STATE_SLEEPY:
             if random.random() < 0.7: can_idle_move = False

        if self.idle_active and can_idle_move and current_time >= self.idle_next_time:
            max_ox, max_oy = self.base_eye_width // 3, self.base_eye_height // 4 
            if self.current_state == STATE_SLEEPY: max_ox //= 2; max_oy //= 2
            rox, roy = random.uniform(-max_ox, max_ox), random.uniform(-max_oy, max_oy)
            tlx, tly = self.eye_default_L_x + rox, self.eye_default_L_y + roy
            mcx, mcxl = EDGE_MARGIN, SCREEN_WIDTH - self.base_eye_width*2 - self.eye_default_spacing - EDGE_MARGIN
            mcy, mcyl = EDGE_MARGIN, SCREEN_HEIGHT - self.base_eye_height - EDGE_MARGIN
            self.eye_target_L_x = self._constrain(tlx, mcx, mcxl if mcxl >= mcx else mcx)
            self.eye_target_L_y = self._constrain(tly, mcy, mcyl if mcyl >= mcy else mcy)
            trx, try_ = self.eye_default_R_x + rox, self.eye_default_R_y + roy
            mcrx_min = self.eye_default_L_x + self.base_eye_width + self.eye_default_spacing + EDGE_MARGIN
            mcrx_max = SCREEN_WIDTH - self.base_eye_width - EDGE_MARGIN
            self.eye_target_R_x = self._constrain(trx, mcrx_min if mcrx_min < mcrx_max else mcrx_max -1 , mcrx_max)
            self.eye_target_R_y = self._constrain(try_, mcy, mcyl if mcyl >= mcy else mcy) 
            self.idle_next_time = current_time + self._get_random_delay(self.idle_interval_s, self.idle_interval_variation_s)

        self.eyeL_x += (self.eye_target_L_x - self.eyeL_x) * tween_factor
        self.eyeL_y += (self.eye_target_L_y - self.eyeL_y) * tween_factor
        self.eyeR_x += (self.eye_target_R_x - self.eyeR_x) * tween_factor
        self.eyeR_y += (self.eye_target_R_y - self.eyeR_y) * tween_factor
        
        # --- DEBUG Stampa Coordinare e Stati ---
        if DEBUG_MODE and current_time - self._last_debug_print_time > 0.5:
            lx_b, ly_b = round(self.eyeL_x), round(self.eyeL_y)
            rx_b, ry_b = round(self.eyeR_x), round(self.eyeR_y)
            b_fr = self.blink_anim_current_frame if self.is_performing_blink_anim else -1
            # AGGIUNTA DI CONTROLLO PER self.eye_sprite_open
            # print(f"DEBUG: self type: {type(self)}, hasattr eye_sprite_open: {hasattr(self, 'eye_sprite_open')}")
            print(f"T{current_time:.1f} "+
                  f"L({lx_b:2},{ly_b:2}) R({rx_b:2},{ry_b:2}) "+
                  f"St:{self.current_state[:5]} Blk:{self.is_performing_blink_anim} Fr:{b_fr}")
            self._last_debug_print_time = current_time
        
        # --- Disegno ---
        self.screen_bitmap.fill(BGCOLOR)
        
        # Determina quale sprite usare per gli occhi
        # AGGIUNTA DI UNA STAMPA DI DEBUG QUI SE L'ERRORE PERSISTE
        # if not hasattr(self, 'eye_sprite_open'):
        # print("!!! ERRORE INTERNO: self.eye_sprite_open non definito prima del disegno!!!")
        # return # Esce per evitare il crash e vedere il messaggio
            
        sprite_to_use_L = self.eye_sprite_open # Default
        sprite_to_use_R = self.eye_sprite_open # Default

        if self.is_performing_blink_anim:
            frame_idx = self._constrain(self.blink_anim_current_frame, 0, self.blink_anim_frame_count - 1)
            sprite_to_use_L = self.blink_animation_sprites[frame_idx]
            sprite_to_use_R = self.blink_animation_sprites[frame_idx]
        else: 
            if self.current_state == STATE_HAPPY:
                sprite_to_use_L = self.sprite_eye_happy_form
                sprite_to_use_R = self.sprite_eye_happy_form
            elif self.current_state == STATE_SURPRISED:
                sprite_to_use_L = self.eye_sprite_open # o self.eye_sprite_surprised_open
                sprite_to_use_R = self.eye_sprite_open # o self.eye_sprite_surprised_open
            elif self.current_state == STATE_SLEEPY:
                if int(current_time*2.5) % 2 == 0: # Alterna un po' più lentamente
                     sprite_to_use_L = self.sprite_eye_mostly_closed
                     sprite_to_use_R = self.sprite_eye_mostly_closed
                else:
                     sprite_to_use_L = self.sprite_eye_line
                     sprite_to_use_R = self.sprite_eye_line
        
        eyeL_blit_y = self.eyeL_y + (self.base_eye_height - sprite_to_use_L.height) / 2.0
        eyeR_blit_y = self.eyeR_y + (self.base_eye_height - sprite_to_use_R.height) / 2.0

        self._blit_sprite(sprite_to_use_L, self.eyeL_x, eyeL_blit_y, skip_index_in_source_palette=BGCOLOR)
        self._blit_sprite(sprite_to_use_R, self.eyeR_x, eyeR_blit_y, skip_index_in_source_palette=BGCOLOR)

        # if FORCE_DISPLAY_REFRESH: self.display.refresh() # Non definito, usa DEBUG_MODE
        
# --- Setup Display e Loop Principale ---
displayio.release_displays()
scl_pin = board.IO4; sda_pin = board.IO3
i2c = busio.I2C(scl_pin, sda_pin)
OLED_I2C_ADDRESS = 0x3C
display_width = SCREEN_WIDTH; display_height = SCREEN_HEIGHT
try:
    display_bus = I2CDisplayBus(i2c, device_address=OLED_I2C_ADDRESS)
    display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=display_width, height=display_height)
    print("Display OLED inizializzato.")
except Exception as e:
    print(f"Errore inizializzazione display: {e}")
    while True: pass

eyes = RoboEyesExpressionsCorrected(display) # Usa il nome classe corretto

TARGET_FPS = 8
FRAME_INTERVAL_S = 1.0 / TARGET_FPS
last_frame_target_time = time.monotonic()

while True:
    eyes.update()
    current_time = time.monotonic()
    next_frame_target_time = last_frame_target_time + FRAME_INTERVAL_S
    sleep_duration = next_frame_target_time - current_time
    if sleep_duration > 0: time.sleep(sleep_duration)
    last_frame_target_time = next_frame_target_time
    if time.monotonic() - last_frame_target_time > FRAME_INTERVAL_S * 1.5:
        last_frame_target_time = time.monotonic()