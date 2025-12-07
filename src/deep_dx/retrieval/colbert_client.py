
import subprocess
import json
import time
from pathlib import Path
from typing import List
import logging

# Configure logging if not already done
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ColBERTClient:
    def __init__(self, container_name: str = "deep-dx-colbert", index_path: str = None):
        self.container_name = container_name
        self.index_path = index_path # Optional override
        self._ensure_container_running()

    def _ensure_container_running(self):
        """Ensures the Golden Stack container is alive and idling."""
        # Check if running
        check = subprocess.run(
            ["docker", "ps", "-q", "-f", f"name={self.container_name}"],
            capture_output=True, text=True
        )
        if check.stdout.strip():
            return

        # Check if stopped/exited
        check_stopped = subprocess.run(
             ["docker", "ps", "-aq", "-f", f"name={self.container_name}"],
             capture_output=True, text=True
        )
        if check_stopped.stdout.strip():
            subprocess.run(["docker", "rm", self.container_name])

        logger.info("🚀 Starting ColBERT Worker Container...")
        
        # We mount the WHOLE project to /app so scripts and data are visible
        project_root = Path.cwd().absolute()
        
        subprocess.run([
            "docker", "run", "-d",
            "--name", self.container_name,
            "-v", f"{project_root}:/app",  # Mount current dir to /app
            "colbert_radical",             # The Image Name
            "tail", "-f", "/dev/null"      # Keep alive command
        ], check=True)
        
        # Give it a sec to stabilize? usually instant.
        time.sleep(1)

    def search(self, query: str, k: int = 20) -> List[dict]:
        """Runs search.py inside the container."""
        
        # 1. Write Input to shared volume (Host side)
        input_data = {"query": query, "k": k}
        # Paths must be relative to where the script expects them
        input_path_host = Path("data/colbert_io/input.json")
        input_path_host.parent.mkdir(parents=True, exist_ok=True)
        
        with open(input_path_host, "w") as f:
            json.dump(input_data, f)

        # 2. Exec inside Docker (Container side paths)
        # Note: We use the mounted path /app/src/deep_dx/docker_scripts/search.py
        cmd = [
            "docker", "exec", self.container_name,
            "python", "/app/src/deep_dx/docker_scripts/search.py",
            "--input", "/app/data/colbert_io/input.json",
            "--output", "/app/data/colbert_io/output.json"
        ]
        
        # Pass custom index path if set
        if self.index_path:
             cmd.extend(["--index_path", self.index_path])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"❌ ColBERT Search Failed:\n{result.stderr}")
            return []

        # 3. Read Output (Host side)
        output_path_host = Path("data/colbert_io/output.json")
        if not output_path_host.exists():
            return []
            
        with open(output_path_host, "r") as f:
            return json.load(f)["results"]

    def rerank(self, query: str, documents: List[str], k: int = 20) -> List[dict]:
        """Runs rerank.py inside the container."""
        # Similar logic to search, but calling rerank.py
        input_data = {"query": query, "documents": documents, "k": k}
        input_path_host = Path("data/colbert_io/rerank_input.json")
        input_path_host.parent.mkdir(parents=True, exist_ok=True)
        
        with open(input_path_host, "w") as f:
            json.dump(input_data, f)

        cmd = [
            "docker", "exec", self.container_name,
            "python", "/app/src/deep_dx/docker_scripts/rerank.py",
            "--input", "/app/data/colbert_io/rerank_input.json",
            "--output", "/app/data/colbert_io/rerank_output.json"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"❌ ColBERT Rerank Failed:\n{result.stderr}")
            return []

        output_path_host = Path("data/colbert_io/rerank_output.json")
        if not output_path_host.exists():
            return []
            
        with open(output_path_host, "r") as f:
            return json.load(f)["results"]
    def index(self, index_name: str, documents: List[str]):
        """Runs index.py inside the container."""
        input_data = {"documents": documents}
        input_path_host = Path("data/colbert_io/index_input.json")
        input_path_host.parent.mkdir(parents=True, exist_ok=True)
        
        with open(input_path_host, "w") as f:
            json.dump(input_data, f)
            
        cmd = [
            "docker", "exec", self.container_name,
            "python", "/app/src/deep_dx/docker_scripts/index.py",
            "--input", "/app/data/colbert_io/index_input.json",
            "--index_name", index_name
        ]
        
        logger.info(f"⏳ building ColBERT index '{index_name}'...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"❌ ColBERT Indexing Failed:\n{result.stderr}")
            raise RuntimeError(f"Indexing Failed: {result.stderr}")
            
        logger.info(f"✅ Indexing complete.\n{result.stderr}")
