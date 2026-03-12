from flask import Flask, request, jsonify
import json
import bot_logic 

app = Flask(__name__)

@app.route("/turn", methods=['POST', 'OPTIONS'])
def on_turn():
    """
    This function is called by the game server on every tick.
    """
    
    # Handle OPTIONS (CORS preflight) requests
    if request.method == 'OPTIONS':
        response = jsonify({})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        print("OPTIONS request received (CORS preflight)")
        return response
    
    # Handle POST requests
    print(f"POST request received from {request.remote_addr}")
    
    # 1. Get the game state
    game_state = request.json
    
    # 2. Log that a new tick has arrived
    print("--- NEW TICK ---")
    
    # 2a. DEBUG: Log incoming game state structure
    print(f"Game state keys: {list(game_state.keys()) if game_state else 'None'}")
    if game_state:
        player = game_state.get('player')
        flames = game_state.get('flames')
        print(f"Player exists: {player is not None}")
        print(f"Flames exists: {flames is not None}, type: {type(flames)}, length: {len(flames) if flames else 0}")
    
    # 3. --- DEBUG BLOCK ---
    try:
        # 3a. CALL THE "BRAIN"
        response_data = bot_logic.get_bot_response(game_state)
        
        # 3b. Log the bot's decision
        print(f"Response data: {response_data}")
        move = response_data.get("move", {})
        direction = move.get("direction", 0) 
        speed = move.get("speed", 0)         
        print(f"DECISION: Move at angle {direction:.1f} with speed {speed}")

        # 3c. Send the response
        response_json = jsonify(response_data)
        response_json.headers.add('Access-Control-Allow-Origin', '*')
        response_json.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        print(f"Sending JSON response: {response_json.get_data(as_text=True)}")
        return response_json

    except Exception as e:
        # 4. IF IT FAILS, PRINT THE ERROR
        print(f"!!! BOT LOGIC CRASHED: {e}")
        import traceback
        traceback.print_exc()
        
        # 5. Send a "do nothing" response to keep the game from crashing
        error_response = jsonify({
            "move": {"direction": 0, "speed": 0},
            "fire": None,
            "debugPoints": []
        })
        error_response.headers.add('Access-Control-Allow-Origin', '*')
        return error_response

# --- Main entry point ---
if __name__ == "__main__":
    print("Starting bot server on http://localhost:3000...")
    # NOTE: debug=True is still enabled
    app.run(port=3000, host='0.0.0.0', debug=True)