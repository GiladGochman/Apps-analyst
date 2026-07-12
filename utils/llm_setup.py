import ollama

from utils.config import get_model_name


def check_and_pull_model(model_name=None, progress_callback=None):
    if model_name is None:
        model_name = get_model_name()

    try:
        ollama.list()
    except Exception:
        return "ERROR_OLLAMA_OFFLINE"

    try:
        available_models = [m['name'] for m in ollama.list()['models']]
        if any(model_name in m for m in available_models):
            return True
    except Exception:
        pass

    try:
        if progress_callback:
            progress_callback(f"[*] Downloading '{model_name}' (2-3GB)...")
        
        current_digest = None
        for progress in ollama.pull(model_name, stream=True):
            # Extract values safely
            completed = progress.get('completed')
            total = progress.get('total')
            digest = progress.get('digest', '')
            status = progress.get('status', '')

            # Check if we have valid numbers to prevent the 'NoneType' error
            if progress_callback and completed is not None and total is not None and total > 0:
                percentage = int((completed / total) * 100)
                
                if digest != current_digest and digest:
                    progress_callback(f"    - Processing layer {digest[:12]}...")
                    current_digest = digest
                
                # Draw the bar
                bar_len = 20
                filled = int(bar_len * completed // total)
                bar = '█' * filled + '-' * (bar_len - filled)
                progress_callback(f"    [{bar}] {percentage}%", update_last=True)
            
            # If there is no numeric progress, just show the status text
            elif progress_callback and status:
                if status != "downloading": # avoid flooding the UI
                    progress_callback(f"    [*] Status: {status}")

        return True
    except Exception as e:
        return str(e)