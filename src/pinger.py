import logging
import subprocess


def send_ping(message: str, timeout: int = 30) -> bool:
    logger = logging.getLogger("claude_reset_scheduler")

    try:
        result = subprocess.run(
            ["claude-code", "chat", "--message", message],
            capture_output=True,
            timeout=timeout,
            text=True,
        )

        if result.returncode != 0:
            logger.error(f"Ping failed with return code {result.returncode}: {result.stderr}")
            return False

        logger.info("Ping sent successfully")
        return True

    except subprocess.TimeoutExpired:
        logger.error(f"Ping timed out after {timeout} seconds")
        return False
    except FileNotFoundError:
        logger.error("claude-code command not found")
        return False
    except Exception as e:
        logger.error(f"Ping failed with exception: {e}")
        return False
