import time
import random
import bitmaptools
import displayio # Necessario per i tipi displayio.Bitmap, displayio.Palette, displayio.Group

# --- Costanti usate dalla classe ---
CP_BGCOLOR = 0
CP_MAINCOLOR = 1

# Stati/Espressioni (queste costanti possono essere usate anche da code.py se importate)
CP_STATE_DEFAULT = "default"
CP_STATE_HAPPY = "happy"
CP_STATE_SLEEPY = "sleepy"
CP_STATE_SURPRISED = "surprised"
CP_STATE_ANGRY = "angry" # Aggiungiamo ANGRY come placeholder

CP_ACTION_BLINK = "blinking"

EDGE_MARGIN = 5 
# Flag di debug specifico per questa libreria
LIB_DEBUG_MODE = False # Imposta a True per stampe interne alla libreria

class RoboEyesCP: # Il nome della classe che verrà importato
    def __init__(self, display_driver_instance): # Accetta l'oggetto display fisico
        self.display_driver = display_driver_instance # Salva il riferimento al display passato
        self.screen_width = 0 
        self.screen_height = 0

        # Palette e Bitmap principali saranno creati in begin()
        self.screen_palette = None
        self.screen_bitmap = None
        self.screen_tile_grid = None
        self.main_group = None # Il gruppo che questa classe gestisce e mostra

        # --- Parametri e Sprite Occhi ---
        self.base_eye_width = 36
        self.base_eye_height = 36
        self.eye_border_radius = 8

        # Sprite verranno creati in _setup_sprites() chiamato da begin()
        self.sprite_eye_open = None
        self.sprite_eye_happy_form = None
        self.sprite_eye_sleepy_form = None
        self.sprite_eye_line = None
        self.sprite_eye_surprised_open = None # Può essere lo stesso di open
        self.blink_animation_sprites = []
        self.blink_anim_frame_count = 0
        
        # Palette per palpebre di Emozione (se decidiamo di usarle separatamente)
        # Per ora, le emozioni cambiano lo sprite intero dell'occhio.
        # self.emotion_lid_palette = None 
        # self.eyelid_angry_L = None
        # self.eyelid_angry_R = None


        # --- Stato Occhi (Posizione, Target) ---
        self.eyeL_x, self.eyeL_y = 0.0, 0.0
        self.eyeR_x, self.eyeR_y = 0.0, 0.0
        self.eye_target_L_x, self.eye_target_L_y = 0.0, 0.0
        self.eye_target_R_x, self.eye_target_R_y = 0.0, 0.0
        
        self.eye_default_spacing = 10
        self.eye_default_L_x = 0.0; self.eye_default_L_y = 0.0
        self.eye_default_R_x = 0.0; self.eye_default_R_y = 0.0

        # --- Sistema di Stati/Azioni ---
        self.current_state = CP_STATE_DEFAULT
        self.state_start_time = 0.0
        self.state_duration = 0.0
        self.expression_eval_interval_s = 5.0 
        self.expression_eval_interval_variation_s = 5.0
        self.next_state_eval_time = 0.0

        self.is_performing_blink_anim = False 
        self.blink_anim_current_frame = 0
        self.blink_anim_next_frame_time = 0.0
        self.blink_frame_duration = 0.07 # Durata di ogni frame del blink

        # --- Movimento Idle ---
        self.idle_active = True
        self.idle_interval_s = 2.0 
        self.idle_interval_variation_s = 2.0
        self.idle_next_time = 0.0
        
        self._last_debug_print_time = 0.0 # Per stampe di debug temporizzate
        # Nota: LIB_DEBUG_MODE è globale a questo file, non self.DEBUG_MODE

    def _get_random_delay(self, base, variation):
        return base + random.uniform(0, variation)

    def _constrain(self, val, min_val, max_val):
        actual_max = max(min_val, max_val) # Evita che min > max in constrain
        return max(min_val, min(val, actual_max))

    def _create_round_rect_sprite(self, width, height, radius, color_index_draw, color_index_bg, palette_to_use):
        _w, _h, _r = int(width), int(height), int(radius)
        _r = min(_r, _w // 2, _h // 2)
        if _r < 0: _r = 0
        sprite = displayio.Bitmap(_w, _h, len(palette_to_use))
        sprite.fill(color_index_bg)
        if _w <= 0 or _h <= 0: return sprite
        if _w > 2 * _r and _h > 0: bitmaptools.fill_region(sprite, _r, 0, _w - _r, _h, color_index_draw)
        if _h > 2 * _r and _w > 0: bitmaptools.fill_region(sprite, 0, _r, _w, _h - _r, color_index_draw)
        if _r > 0:
            def _draw_filled_circle_on_sprite(s_b, cx, cy, r_c, c_idx):
                for xo in range(-r_c, r_c + 1):
                    for yo in range(-r_c, r_c + 1):
                        if xo*xo + yo*yo <= r_c*r_c:
                            px,py = cx+xo, cy+yo
                            if 0<=px<s_b.width and 0<=py<s_b.height: s_b[px,py]=c_idx
            _draw_filled_circle_on_sprite(sprite, _r, _r, _r, color_index_draw)
            _draw_filled_circle_on_sprite(sprite, _w - _r - 1, _r, _r, color_index_draw)
            _draw_filled_circle_on_sprite(sprite, _r, _h - _r - 1, _r, color_index_draw)
            _draw_filled_circle_on_sprite(sprite, _w - _r - 1, _h - _r - 1, _r, color_index_draw)
        elif _w > 0 and _h > 0 : sprite.fill(color_index_draw)
        return sprite

    def _setup_sprites(self):
        # Sprite Principali
        self.sprite_eye_open = self._create_round_rect_sprite(
            self.base_eye_width, self.base_eye_height, self.eye_border_radius, CP_MAINCOLOR, CP_BGCOLOR, self.screen_palette)
        
        h_half = max(1, int(self.base_eye_height * 0.55))
        h_line = max(1, 6) 
        blink_h_intermediate = max(1, int(self.base_eye_height * 0.35))

        self.sprite_eye_happy_form = self._create_round_rect_sprite(
            self.base_eye_width, h_half, self.eye_border_radius // 2 if self.eye_border_radius > 1 else 1, 
            CP_MAINCOLOR, CP_BGCOLOR, self.screen_palette)
        self.sprite_eye_sleepy_form = self._create_round_rect_sprite( # Era mostly_closed
            self.base_eye_width, h_line, 2 if h_line > 3 else 1, CP_MAINCOLOR, CP_BGCOLOR, self.screen_palette)
        # self.sprite_eye_line era uguale a sleepy_form, possiamo unificarli o tenerli separati
        # Per ora, usiamo sleepy_form anche per la linea del blink.
        
        self.sprite_eye_surprised_open = self.sprite_eye_open 
        
        sprite_blink_intermediate = self._create_round_rect_sprite(
            self.base_eye_width, blink_h_intermediate, self.eye_border_radius // 3 if self.eye_border_radius > 2 else 1,
            CP_MAINCOLOR, CP_BGCOLOR, self.screen_palette)
        
        self.blink_animation_sprites = [
            self.sprite_eye_open, 
            sprite_blink_intermediate,
            self.sprite_eye_sleepy_form, # Usa lo sprite sleepy come "chiuso" nel blink
            sprite_blink_intermediate,
            self.sprite_eye_open,
        ]
        self.blink_anim_frame_count = len(self.blink_animation_sprites)


    def _blit_sprite(self, source_bitmap, dest_x, dest_y, skip_index_in_source_palette=None):
        _dest_x_int = round(dest_x); _dest_y_int = round(dest_y)
        if _dest_x_int + source_bitmap.width <= 0 or \
           _dest_x_int >= self.screen_width or \
           _dest_y_int + source_bitmap.height <= 0 or \
           _dest_y_int >= self.screen_height or \
           _dest_y_int < 0:
            return 
        try:
            bitmaptools.blit(self.screen_bitmap, source_bitmap, _dest_x_int, _dest_y_int,
                             skip_source_index=skip_index_in_source_palette)
        except Exception as e:
            if LIB_DEBUG_MODE: print(f"*** Errore Blit xy=({_dest_x_int},{_dest_y_int}): {e}")

    def _handle_blink_animation(self, current_time):
        if not self.is_performing_blink_anim: return
        if current_time >= self.blink_anim_next_frame_time:
            self.blink_anim_current_frame += 1
            if self.blink_anim_current_frame >= self.blink_anim_frame_count:
                self.is_performing_blink_anim = False
                self.blink_anim_current_frame = 0 
            else:
                self.blink_anim_next_frame_time = current_time + self.blink_frame_duration
    
    def _trigger_blink(self, current_time):
        if not self.is_performing_blink_anim: 
            self.is_performing_blink_anim = True
            self.blink_anim_current_frame = 0 
            self.blink_anim_next_frame_time = current_time 
            if LIB_DEBUG_MODE: print(f"ACTION: Blink Start @{current_time:.2f}")

    def _update_state_machine(self, current_time):
        if self.current_state != CP_STATE_DEFAULT and \
           not self.is_performing_blink_anim and \
           current_time >= self.state_start_time + self.state_duration:
            self.current_state = CP_STATE_DEFAULT
            if LIB_DEBUG_MODE: print(f"STATE -> DEFAULT @{current_time:.2f}")

        if self.current_state == CP_STATE_DEFAULT and \
           not self.is_performing_blink_anim and \
           current_time >= self.next_state_eval_time:
            action_eff_duration = 0.0 
            rand_val = random.random()
            chosen_state = None
            if rand_val < 0.35: 
                self._trigger_blink(current_time)
                action_eff_duration = (self.blink_anim_frame_count -1) * self.blink_frame_duration
            elif rand_val < 0.60: chosen_state = CP_STATE_HAPPY; self.state_duration = random.uniform(1.5, 3.0)
            elif rand_val < 0.80: chosen_state = CP_STATE_SLEEPY; self.state_duration = random.uniform(2.0, 4.0)
            else: chosen_state = CP_STATE_SURPRISED; self.state_duration = random.uniform(1.0, 2.0)
            
            if chosen_state:
                self.current_state = chosen_state
                self.state_start_time = current_time
                action_eff_duration = self.state_duration
                if LIB_DEBUG_MODE: print(f"STATE -> {self.current_state} for {self.state_duration:.1f}s")
            self.next_state_eval_time = current_time + action_eff_duration + \
                self._get_random_delay(self.expression_eval_interval_s, self.expression_eval_interval_variation_s)

    # --- Metodi Pubblici per Controllare gli Occhi ---
    def begin(self, width, height, frame_rate_target):
        self.screen_width = width
        self.screen_height = height

        # Setup Palette principale (se non già fatta in init)
        if self.screen_palette is None:
            self.screen_palette = displayio.Palette(2)
            self.screen_palette[CP_BGCOLOR] = 0x000000
            self.screen_palette[CP_MAINCOLOR] = 0xFFFFFF
        
        # Setup Bitmap e Gruppo principale per il display
        self.screen_bitmap = displayio.Bitmap(self.screen_width, self.screen_height, len(self.screen_palette))
        self.screen_tile_grid = displayio.TileGrid(self.screen_bitmap, pixel_shader=self.screen_palette)
        self.main_group = displayio.Group()
        self.main_group.append(self.screen_tile_grid)
        self.display_driver.root_group = self.main_group # Assegna al display fisico

        self._setup_sprites() # Crea tutti gli sprite necessari

        # Calcola posizioni di default
        _total_default_width = self.base_eye_width * 2 + self.eye_default_spacing
        self.eye_default_L_x = float((self.screen_width - _total_default_width) // 2)
        self.eye_default_L_y = float((self.screen_height - self.base_eye_height) // 2)
        self.eye_default_R_x = self.eye_default_L_x + self.base_eye_width + self.eye_default_spacing
        self.eye_default_R_y = self.eye_default_L_y

        self.eye_target_L_x, self.eye_target_L_y = self.eye_default_L_x, self.eye_default_L_y
        self.eye_target_R_x, self.eye_target_R_y = self.eye_default_R_x, self.eye_default_R_y
        self.eyeL_x, self.eyeL_y = self.eye_default_L_x, self.eye_default_L_y
        self.eyeR_x, self.eyeR_y = self.eye_default_R_x, self.eye_default_R_y

        self.next_state_eval_time = time.monotonic() + self._get_random_delay(self.expression_eval_interval_s, self.expression_eval_interval_variation_s)
        self.idle_next_time = time.monotonic() + self._get_random_delay(self.idle_interval_s, self.idle_interval_variation_s)
        
        if LIB_DEBUG_MODE: print(f"RoboEyesCP begin: Screen {self.screen_width}x{self.screen_height}")


    def update(self):
        current_time = time.monotonic()
        tween_factor = 0.25

        self._update_state_machine(current_time)
        if self.is_performing_blink_anim:
            self._handle_blink_animation(current_time)
        
        can_idle_move = not self.is_performing_blink_anim
        if self.current_state == CP_STATE_SURPRISED: can_idle_move = False
        if self.current_state == CP_STATE_SLEEPY:
             if random.random() < 0.75: can_idle_move = False # Più probabilità di stare fermo

        if self.idle_active and can_idle_move and current_time >= self.idle_next_time:
            max_ox, max_oy = self.base_eye_width // 3, self.base_eye_height // 4 
            if self.current_state == CP_STATE_SLEEPY: max_ox //= 2; max_oy //= 2
            rox, roy = random.uniform(-max_ox, max_ox), random.uniform(-max_oy, max_oy)
            tlx, tly = self.eye_default_L_x + rox, self.eye_default_L_y + roy
            mcx = EDGE_MARGIN; mcxl = self.screen_width - self.base_eye_width*2 - self.eye_default_spacing - EDGE_MARGIN
            mcy = EDGE_MARGIN; mcyl = self.screen_height - self.base_eye_height - EDGE_MARGIN
            self.eye_target_L_x = self._constrain(tlx, mcx, mcxl if mcxl >= mcx else mcx)
            self.eye_target_L_y = self._constrain(tly, mcy, mcyl if mcyl >= mcy else mcy)
            trx, try_ = self.eye_default_R_x + rox, self.eye_default_R_y + roy
            mcrx_min = self.eye_default_L_x + self.base_eye_width + self.eye_default_spacing + EDGE_MARGIN
            mcrx_max = self.screen_width - self.base_eye_width - EDGE_MARGIN
            self.eye_target_R_x = self._constrain(trx, mcrx_min if mcrx_min < mcrx_max else mcrx_max -1 , mcrx_max)
            self.eye_target_R_y = self._constrain(try_, mcy, mcyl if mcyl >= mcy else mcy) 
            self.idle_next_time = current_time + self._get_random_delay(self.idle_interval_s, self.idle_interval_variation_s)

        self.eyeL_x += (self.eye_target_L_x - self.eyeL_x) * tween_factor
        self.eyeL_y += (self.eye_target_L_y - self.eyeL_y) * tween_factor
        self.eyeR_x += (self.eye_target_R_x - self.eyeR_x) * tween_factor
        self.eyeR_y += (self.eye_target_R_y - self.eyeR_y) * tween_factor
        
        if LIB_DEBUG_MODE and current_time - self._last_debug_print_time > 1.0: # Stampa ogni secondo
            lx_b, ly_b = round(self.eyeL_x), round(self.eyeL_y); rx_b, ry_b = round(self.eyeR_x), round(self.eyeR_y)
            b_fr = self.blink_anim_current_frame if self.is_performing_blink_anim else -1
            print(f"T{current_time:.1f} L({lx_b:2},{ly_b:2}) R({rx_b:2},{ry_b:2}) St:{self.current_state[:5]} Blk:{self.is_performing_blink_anim} Fr:{b_fr}")
            self._last_debug_print_time = current_time
        
        self.screen_bitmap.fill(CP_BGCOLOR)
        
        sprite_to_use_L = self.sprite_eye_open
        sprite_to_use_R = self.sprite_eye_open

        if self.is_performing_blink_anim:
            frame_idx = self._constrain(self.blink_anim_current_frame, 0, self.blink_anim_frame_count - 1)
            sprite_to_use_L = self.blink_animation_sprites[frame_idx]
            sprite_to_use_R = self.blink_animation_sprites[frame_idx]
        else: 
            if self.current_state == CP_STATE_HAPPY:
                sprite_to_use_L = self.sprite_eye_happy_form
                sprite_to_use_R = self.sprite_eye_happy_form
            elif self.current_state == CP_STATE_SURPRISED:
                sprite_to_use_L = self.sprite_eye_surprised_open 
                sprite_to_use_R = self.sprite_eye_surprised_open
            elif self.current_state == CP_STATE_SLEEPY:
                # Alterna per un effetto "pesante" o occhi chiusi
                if int(current_time*1.5) % 2 == 0: # Rallenta l'alternanza per sleepy
                     sprite_to_use_L = self.sprite_eye_sleepy_form # Era mostly_closed
                     sprite_to_use_R = self.sprite_eye_sleepy_form
                else: # Mantiene la linea più a lungo
                     sprite_to_use_L = self.sprite_eye_sleepy_form # Era line, ora sleepy_form per consistenza
                     sprite_to_use_R = self.sprite_eye_sleepy_form
        
        eyeL_blit_y = self.eyeL_y + (self.base_eye_height - sprite_to_use_L.height) / 2.0
        eyeR_blit_y = self.eyeR_y + (self.base_eye_height - sprite_to_use_R.height) / 2.0

        self._blit_sprite(sprite_to_use_L, self.eyeL_x, eyeL_blit_y, skip_index_in_source_palette=CP_BGCOLOR)
        self._blit_sprite(sprite_to_use_R, self.eyeR_x, eyeR_blit_y, skip_index_in_source_palette=CP_BGCOLOR)