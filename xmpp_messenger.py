import xml.etree.ElementTree as ET
import socket
import threading
import time


class SimpleMessenger:
    def __init__(self, my_nick="me", port=5299):
        self.my_nick = my_nick
        self.port = port
        self.peers = {}
        self.current_chat = None
        self.running = True
        self.lock = threading.Lock()

    def get_my_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 1))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def create_message(self, to_ip, text):
        message = ET.Element("message")
        message.set("to", to_ip)
        message.set("from", self.my_nick)
        message.set("type", "chat")

        body = ET.SubElement(message, "body")
        body.text = text

        return ET.tostring(message, encoding='unicode')

    def parse_message(self, xml_string):
        try:
            if '<' in xml_string:
                xml_string = xml_string[xml_string.find('<'):]

            root = ET.fromstring(xml_string)
            if root.tag == 'message':
                body = root.find('body')
                from_attr = root.get('from', 'unknown')
                if body is not None:
                    return from_attr, body.text
        except:
            pass
        return "unknown", xml_string

    def handle_connection(self, conn, addr):
        peer_ip = addr[0]

        conn.send(f"HELLO|{self.my_nick}".encode())

        try:
            data = conn.recv(1024).decode()
            if data.startswith("HELLO|"):
                their_nick = data.split("|")[1]
            else:
                their_nick = "friend"

            with self.lock:
                self.peers[peer_ip] = {
                    'socket': conn,
                    'nickname': their_nick,
                    'last_active': time.time()
                }

            print(f"\n{'=' * 50}")
            print(f" {their_nick} ({peer_ip}) connected!")
            print(f"Type 'chat {their_nick}' to start talking")
            print(f"{'=' * 50}")
            print("\nYou: ", end="")

            while self.running:
                try:
                    data = conn.recv(4096)
                    if not data:
                        break

                    sender_nick, message = self.parse_message(data.decode('utf-8', errors='ignore'))

                    print(f"\n{'─' * 40}")
                    print(f"NEW MESSAGE from {their_nick}:")
                    print(f"   {message}")
                    print(f"{'─' * 40}")
                    print("\nYou: ", end="")

                except:
                    break

        finally:
            with self.lock:
                if peer_ip in self.peers:
                    del self.peers[peer_ip]
            conn.close()
            print(f"\n️  {their_nick if 'their_nick' in locals() else peer_ip} disconnected")
            print("You: ", end="")

    def start_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', self.port))
        server.listen(5)
        server.settimeout(1)

        print(f" Listening for connections on port {self.port}")

        while self.running:
            try:
                conn, addr = server.accept()
                thread = threading.Thread(target=self.handle_connection, args=(conn, addr))
                thread.daemon = True
                thread.start()
            except socket.timeout:
                continue
            except:
                break

        server.close()

    def connect_to_friend(self, ip_address):

        print(f"\n Connecting to {ip_address}...")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip_address, self.port))
            sock.settimeout(None)


            data = sock.recv(1024).decode()
            if data.startswith("HELLO|"):
                their_nick = data.split("|")[1]
                sock.send(f"HELLO|{self.my_nick}".encode())
            else:
                their_nick = "friend"
                sock.send(f"HELLO|{self.my_nick}".encode())

            with self.lock:
                self.peers[ip_address] = {
                    'socket': sock,
                    'nickname': their_nick,
                    'last_active': time.time()
                }

            print(f"\n{'=' * 50}")
            print(f" Connected to {their_nick} ({ip_address})!")
            print(f"Type 'chat {their_nick}' to start talking")
            print(f"{'=' * 50}")
            print("\nYou: ", end="")

            thread = threading.Thread(target=self.handle_connection, args=(sock, (ip_address, self.port)))
            thread.daemon = True
            thread.start()

            return True

        except Exception as e:
            print(f"\n Failed to connect: {e}")
            print("You: ", end="")
            return False

    def send_message(self, to_ip, message):
        with self.lock:
            if to_ip not in self.peers:
                print(f"\n Not connected to {to_ip}. Use 'connect IP' first.")
                print("You: ", end="")
                return False

            sock = self.peers[to_ip]['socket']
            their_nick = self.peers[to_ip]['nickname']

        try:
            xml_msg = self.create_message(to_ip, message)
            sock.send(xml_msg.encode())


            print(f"\n{'─' * 40}")
            print(f"You to {their_nick}:")
            print(f"   {message}")
            print(f"{'─' * 40}")
            print("\nYou: ", end="")
            return True

        except Exception as e:
            print(f"\n✗ Failed to send: {e}")
            with self.lock:
                if to_ip in self.peers:
                    del self.peers[to_ip]
            print("You: ", end="")
            return False

    def switch_chat(self, nickname):
        with self.lock:
            for ip, info in self.peers.items():
                if info['nickname'].lower() == nickname.lower():
                    self.current_chat = ip
                    print(f"\nNow chatting with {info['nickname']}")
                    print("Type your message (or 'back' to see commands)")
                    print(f"{'─' * 40}")
                    print("\nYou: ", end="")
                    return True

        print(f"\nNo connection with {nickname}")
        print("Use 'friends' to see who's connected")
        print("\nYou: ", end="")
        return False

    def show_friends(self):

        with self.lock:
            if not self.peers:
                print("\n No friends connected")
                print("Use 'connect IP' to connect to someone")
            else:
                print(f"\n{'=' * 50}")
                print("Connected Friends:")
                for ip, info in self.peers.items():
                    status = "Online" if info['socket'].fileno() != -1 else " Away"
                    print(f"  • {info['nickname']} ({ip}) {status}")
                print(f"{'=' * 50}")

        print("\nYou: ", end="")

    def show_help(self):
        print(f"\n{'=' * 50}")
        print(" Available Commands:")
        print("  connect IP           - Connect to a friend's IP")
        print("  friends              - Show connected friends")
        print("  chat NICKNAME        - Start chatting with someone")
        print("  help                 - Show this help")
        print("  exit                 - Quit program")
        print("")
        print(" When in chat mode, just type messages!")
        print("   Type 'back' to return to command mode")
        print(f"{'=' * 50}")
        print("\nYou: ", end="")

    def run(self):
        print(f"\n{'=' * 50}")
        print(f"💬 SIMPLE MESSENGER - {self.my_nick}")
        print(f"📡 Your IP: {self.get_my_ip()}")
        print(f"{'=' * 50}")


        server_thread = threading.Thread(target=self.start_server)
        server_thread.daemon = True
        server_thread.start()

        time.sleep(0.5)

        print("\nType 'help' for commands or 'connect IP' to start")
        print("You: ", end="")

        while self.running:
            try:
                user_input = input().strip()

                if not user_input:
                    print("You: ", end="")
                    continue


                if self.current_chat:
                    if user_input.lower() == 'back':
                        self.current_chat = None
                        print(" Back to command mode")
                        print("Type 'help' for commands")
                        print("\nYou: ", end="")
                        continue


                    self.send_message(self.current_chat, user_input)
                    continue


                if user_input.lower() == 'exit':
                    print(" Goodbye!")
                    self.running = False
                    break

                elif user_input.lower() == 'help':
                    self.show_help()

                elif user_input.lower() == 'friends':
                    self.show_friends()

                elif user_input.startswith('connect '):
                    parts = user_input.split()
                    if len(parts) == 2:
                        ip = parts[1]

                        if self.connect_to_friend(ip):

                            with self.lock:
                                if ip in self.peers:
                                    self.current_chat = ip
                                    print(f" Automatically chatting with {self.peers[ip]['nickname']}")
                                    print("Type your message (or 'back' for commands)")
                                    print("\nYou: ", end="")
                    else:
                        print(" Usage: connect IP_ADDRESS")
                        print("You: ", end="")

                elif user_input.startswith('chat '):
                    parts = user_input.split()
                    if len(parts) >= 2:
                        nickname = ' '.join(parts[1:])
                        self.switch_chat(nickname)
                    else:
                        print(" Usage: chat NICKNAME")
                        print("You: ", end="")

                else:
                    print(" Unknown command. Type 'help' for commands.")
                    print("You: ", end="")

            except KeyboardInterrupt:
                print("\n Goodbye!")
                self.running = False
                break
            except Exception as e:
                print(f"\n⚠  Error: {e}")
                print("You: ", end="")



if __name__ == "__main__":
    print("=== SIMPLE P2P MESSENGER ===")

    nickname = input("Enter your nickname: ").strip()
    if not nickname:
        nickname = "User"

    messenger = SimpleMessenger(my_nick=nickname)
    messenger.run()