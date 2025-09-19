"""
SSH Helper with better command handling
"""
import time
import re

class SSHCommandHandler:
    def __init__(self, shell):
        self.shell = shell
        self.prompt_pattern = re.compile(r'[>#]$', re.MULTILINE)
    
    def wait_for_prompt(self, timeout=10):
        """Wait for router prompt to appear"""
        start_time = time.time()
        buffer = ""
        
        while time.time() - start_time < timeout:
            if self.shell.recv_ready():
                data = self.shell.recv(1024).decode('utf-8', errors='ignore')
                buffer += data
                
                # Check if we have a prompt
                if self.prompt_pattern.search(buffer):
                    return buffer, True
            time.sleep(0.1)
        
        return buffer, False
    
    def send_command_clean(self, command, wait_time=3):
        """Send command and wait for clean output"""
        try:
            # 1. Clear any existing buffer
            print(f"DEBUG: Clearing initial buffer...")
            self.wait_for_prompt(timeout=2)
            
            # 2. Send command
            command_clean = command.strip()
            print(f"DEBUG: Sending command: '{command_clean}'")
            
            command_with_newline = command_clean + "\r\n"
            self.shell.send(command_with_newline.encode('utf-8'))
            
            # 3. Wait for output
            time.sleep(wait_time)
            
            # 4. Collect output until we see prompt again
            output, got_prompt = self.wait_for_prompt(timeout=10)
            
            if not got_prompt:
                print("WARNING: Did not receive prompt after command")
            
            # 5. Clean the output
            lines = output.split('\n')
            clean_lines = []
            
            # Skip the first line if it contains the command echo
            start_idx = 0
            for i, line in enumerate(lines):
                if command_clean in line.strip():
                    start_idx = i + 1
                    break
            
            # Process remaining lines
            for i in range(start_idx, len(lines)):
                line = lines[i].strip()
                # Skip prompt lines
                if re.match(r'^.*[>#]\s*$', line):
                    continue
                if line:
                    clean_lines.append(line)
            
            result = '\n'.join(clean_lines)
            print(f"DEBUG: Clean result (first 200 chars): '{result[:200]}'...")
            
            return {
                "success": True,
                "output": result,
                "raw_output": output,
                "command": command_clean
            }
            
        except Exception as e:
            print(f"ERROR in send_command_clean: {e}")
            return {
                "success": False,
                "error": str(e),
                "command": command
            }