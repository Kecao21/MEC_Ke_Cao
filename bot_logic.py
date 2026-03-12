import math

# Constants
EMERGENCY_DODGE_RADIUS = 175.0   # If a flame is this close, drop everything and run.
ITEM_HUNT_SAFETY_RADIUS = 100.0 # If closest flame is OUTSIDE this, it's "safe" to get items.

# Force Weights 
WALL_WEIGHT = 5.0     # How strongly to run from corners
WALL_MARGIN = 80.0    # How close to get to a wall before running
SPAWN_WEIGHT = 3.0    # How strongly to avoid flame exits
SPAWN_MARGIN = 75.0   # The "danger radius" around a spawn exit

# HYBRID TARGETING 
CAMPFIRE_DANGER_THRESHOLD = 150.0 # If a normal flame is closer than this, shoot it first.

# ITEM PRIORITY 
ITEM_PRIORITY_BUCKETS = [
    ['nuke'],  # Priority 1: "nuke"
    ['superbullet'], # Priority 2
    ['rapidfire', 'rapidwalk'] # Priority 3
]


def get_bot_response(game_state: dict) -> dict:
    
    # --- 1. Guard Clauses & State Parsing ---
    player = game_state.get('player')
    flames = game_state.get('flames')
    items = game_state.get('items')
    map_data = game_state.get('map')

    if not player or not player.get('position') or not map_data or not map_data.get('size'):
        return {"move": {"direction": 0, "speed": 0}, "fire": None, "debugPoints": []}
    
    player_pos = player['position']
    map_size = map_data['size']
    spawn_points = map_data.get('spawnPoints', [])
    
    # --- 2. Shared Calculations (Needed for all states) ---
    final_vector_x, final_vector_y = 0, 0 # This will be set by ONE state
    
    # --- 2a. Find Closest Flame (for safety checks) ---
    closest_flame_dist = float('inf')
    closest_flame_obj = None
    if flames:
        for f in flames:
            f_pos = f.get('position')
            if not f_pos: continue
            dist = math.hypot(player_pos['x'] - f_pos['x'], player_pos['y'] - f_pos['y'])
            if dist < closest_flame_dist:
                closest_flame_dist = dist
                closest_flame_obj = f

    # --- 2b. Wall Repulsion (Used in State 2 & 3) ---
    wall_vector_x, wall_vector_y = 0, 0
    if player_pos['x'] < WALL_MARGIN:
        wall_vector_x += (WALL_MARGIN - player_pos['x'])
    if player_pos['x'] > map_size['width'] - WALL_MARGIN:
        wall_vector_x -= (player_pos['x'] - (map_size['width'] - WALL_MARGIN))
    if player_pos['y'] < WALL_MARGIN:
        wall_vector_y += (WALL_MARGIN - player_pos['y'])
    if player_pos['y'] > map_size['height'] - WALL_MARGIN:
        wall_vector_y -= (player_pos['y'] - (map_size['height'] - WALL_MARGIN))
        
    # --- 2c. Spawn Repulsion (Used in State 2 & 3) ---
    spawn_vector_x, spawn_vector_y = 0, 0
    for sp in spawn_points:
        sp_center_x = sp['x'] + sp['width'] / 2
        sp_center_y = sp['y'] + sp['height'] / 2
        dist_to_spawn_center = math.hypot(player_pos['x'] - sp_center_x, player_pos['y'] - sp_center_y)
        if dist_to_spawn_center < SPAWN_MARGIN:
            push_force = (SPAWN_MARGIN - dist_to_spawn_center)
            vec_x = player_pos['x'] - sp_center_x
            vec_y = player_pos['y'] - sp_center_y
            if dist_to_spawn_center > 0:
                norm = dist_to_spawn_center
                spawn_vector_x += (vec_x / norm) * push_force
                spawn_vector_y += (vec_y / norm) * push_force

    # 3. THE STATE MACHINE (IF/ELIF/ELSE) 

    # --- STATE 1: EMERGENCY DODGE ---
    if closest_flame_dist < EMERGENCY_DODGE_RADIUS and closest_flame_obj:
        run_from_pos = closest_flame_obj['position']
        vec_x = player_pos['x'] - run_from_pos['x']
        vec_y = player_pos['y'] - run_from_pos['y']
        norm = math.hypot(vec_x, vec_y)
        if norm > 0:
            final_vector_x = (vec_x / norm)
            final_vector_y = (vec_y / norm)
    
    # --- STATE 2: ITEM HUNTING ---
    elif closest_flame_dist > ITEM_HUNT_SAFETY_RADIUS and items:
        priority_target_item = None
        
        for bucket in ITEM_PRIORITY_BUCKETS:
            closest_in_bucket = None
            min_dist = float('inf')
            for item in items:
                if item.get('type') in bucket:
                    i_pos = item.get('position')
                    if not i_pos: continue
                    dist = math.hypot(player_pos['x'] - i_pos['x'], player_pos['y'] - i_pos['y'])
                    if dist < min_dist:
                        min_dist = dist
                        closest_in_bucket = item
            if closest_in_bucket:
                priority_target_item = closest_in_bucket
                break # Found the best item, stop searching
        
        if priority_target_item:
            item_pos = priority_target_item['position']
            vec_x = item_pos['x'] - player_pos['x']
            vec_y = item_pos['y'] - player_pos['y']
            norm = math.hypot(vec_x, vec_y)
            
            # 1. Add item vector (normalized)
            item_move_x, item_move_y = 0, 0
            if norm > 0:
                item_move_x = (vec_x / norm)
                item_move_y = (vec_y / norm)
            
            # --- THIS IS THE FIX ---
            final_vector_x = item_move_x + \
                             (wall_vector_x * WALL_WEIGHT) + \
                             (spawn_vector_x * SPAWN_WEIGHT)
                             
            final_vector_y = item_move_y + \
                             (wall_vector_y * WALL_WEIGHT) + \
                             (spawn_vector_y * SPAWN_WEIGHT)
            # --- END FIX ---

        else:
            # No priority items found? Revert to "Safe" state.
            final_vector_x = (spawn_vector_x * SPAWN_WEIGHT) + (wall_vector_x * WALL_WEIGHT)
            final_vector_y = (spawn_vector_y * SPAWN_WEIGHT) + (wall_vector_y * WALL_WEIGHT)

    # --- STATE 3: Default State ---
    else:
        final_vector_x = (spawn_vector_x * SPAWN_WEIGHT) + (wall_vector_x * WALL_WEIGHT)
        final_vector_y = (spawn_vector_y * SPAWN_WEIGHT) + (wall_vector_y * WALL_WEIGHT)

    # --- 4. Calculate Final Movement Angle & Speed ---
    if final_vector_x == 0 and final_vector_y == 0:
        final_run_angle, final_run_speed = 0, 0
    else:
        angle_rad = math.atan2(final_vector_y, final_vector_x)
        final_run_angle = (math.degrees(angle_rad) + 360) % 360
        final_run_speed = 1.0

    # --- 5. Hybrid Priority Offense Logic (Unchanged) ---
    fire_angle = None
    if player.get('fireCooldown', 1) == 0 and flames:
        best_campfire_target = None
        min_campfire_dist = float('inf')
        for f in flames:
            if f.get('type') == 'campfire' and f.get('speed', 1) == 0:
                f_pos = f.get('position')
                if not f_pos: continue
                dist = math.hypot(player_pos['x'] - f_pos['x'], player_pos['y'] - f_pos['y'])
                if dist < min_campfire_dist:
                    min_campfire_dist = dist
                    best_campfire_target = f
        
        final_target = None
        if best_campfire_target:
            if closest_flame_dist < CAMPFIRE_DANGER_THRESHOLD:
                final_target = closest_flame_obj
            else:
                final_target = best_campfire_target
        else:
            final_target = closest_flame_obj
            
        if final_target:
            target_pos = final_target['position']
            shoot_vector_x = target_pos['x'] - player_pos['x']
            shoot_vector_y = target_pos['y'] - player_pos['y']
            shoot_rad = math.atan2(shoot_vector_y, shoot_vector_x)
            fire_angle = (math.degrees(shoot_rad) + 360) % 360
            
    # 6. Return the Response
    response = {
        "move": {
            "direction": final_run_angle,
            "speed": final_run_speed
        },
        "fire": fire_angle,
        "debugPoints": []
    }
    
    return response