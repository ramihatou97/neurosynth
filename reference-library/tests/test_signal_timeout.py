
import concurrent.futures
import time
import signal
import os

def timeout_handler(signum, frame):
    raise TimeoutError("Hard timeout in worker")

def worker_with_signal(x):
    # Set alarm for 2 seconds
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(2)
    
    try:
        if x == "hang":
            print(f"Worker {os.getpid()} hanging...", flush=True)
            time.sleep(5) # Sleep longer than alarm
        else:
            print(f"Worker {os.getpid()} done", flush=True)
            return x
    except TimeoutError:
        print(f"Worker {os.getpid()} caught timeout!", flush=True)
        return "timed_out"
    finally:
        signal.alarm(0) # Disable alarm

def test_signal_timeout():
    print("Starting signal test...", flush=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(worker_with_signal, "normal"): "normal",
            executor.submit(worker_with_signal, "hang"): "hang"
        }
        
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                print(f"Result: {result}", flush=True)
            except Exception as e:
                print(f"Exception: {e}", flush=True)

if __name__ == "__main__":
    test_signal_timeout()
