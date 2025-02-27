import time
import json
import asyncio
import aiohttp
from eth_account.messages import encode_defunct
from web3 import Web3
from datetime import datetime
import logging
import random
import ssl
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.text import Text
from rich.style import Style


console = Console()
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)

class LayerEdgeBot:
    def load_config(self):
        """加载配置文件"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except Exception as e:
            logging.error(f"Error loading config: {str(e)}")
            return {
                "use_proxy": True,
                "retry_times": 3,
                "check_interval": 300,
                "restart_interval": 43200,
                "claim_success_wait": 43200,
                "claim_fail_wait": 10800,
                "twitter": "https://x.com/SniffTunes",
                "author": "SniffTunes",
                "version": "2.0.0",
                "log_level": "INFO"
            }

    def print_banner(self):
        """打印启动横幅"""
        banner = Text()
        banner.append("╔══════════════════════════════════════════════════════════════╗\n", style="cyan")
        banner.append("║                     LayerEdgeBot                             ║\n", style="cyan bold")
        banner.append("╠══════════════════════════════════════════════════════════════╣\n", style="cyan")
        banner.append("║  ", style="cyan")
        banner.append("🐦 Twitter: ", style="blue")
        banner.append(self.config['twitter'], style=f"link {self.config['twitter']}")
        banner.append("                        ║\n", style="cyan")
        banner.append("║  ", style="cyan")
        banner.append("👨‍💻 Author: ", style="green")
        banner.append(self.config['author'], style="green bold")
        banner.append("                                      ║\n", style="cyan")
        banner.append("║  ", style="cyan")
        banner.append("🌟 Version: ", style="yellow")
        banner.append(self.config['version'], style="yellow bold")
        banner.append("                                           ║\n", style="cyan")
        banner.append("╚══════════════════════════════════════════════════════════════╝", style="cyan")
        
        console.print(Panel(banner, border_style="cyan", padding=(1, 2)))

    def __init__(self):
        self.config = self.load_config()
        self.w3 = Web3()
        self.accounts = self.load_accounts()
        self.proxies = self.load_proxies() if self.config['use_proxy'] else [None] * len(self.accounts)
        self.user_agents = self.load_user_agents()
        self.headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'zh-HK,zh;q=0.9,zh-TW;q=0.8',
            'content-type': 'application/json',
            'origin': 'https://dashboard.layeredge.io',
            'priority': 'u=1, i',
            'referer': 'https://dashboard.layeredge.io/',
            'sec-ch-ua': '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site'
        }
        self.node_points = {}  
        self.emojis = {
            'start': '🚀',
            'stop': '🛑',
            'restart': '🔄',
            'check': '✅',
            'error': '❌',
            'warning': '⚠️',
            'points': '💎',
            'wait': '⏳'
        }
        
    def load_accounts(self):
        """加载账户私钥"""
        with open('accounts.txt', 'r') as f:
            return [line.strip() for line in f.readlines()]
            
    def load_proxies(self):
        """加载代理"""
        with open('proxy.txt', 'r') as f:
            return [line.strip() for line in f.readlines()]
            
    def load_user_agents(self):
        """加载UA列表"""
        with open('ua.txt', 'r') as f:
            return [line.strip() for line in f.readlines()]
            
    async def get_wallet_address(self, private_key):
        """通过私钥获取钱包地址"""
        account = self.w3.eth.account.from_key(private_key)
        return account.address
        
    async def sign_message(self, message, private_key):
        """签名消息"""
        message_hash = encode_defunct(text=message)
        signed_message = self.w3.eth.account.sign_message(
            message_hash,
            private_key=private_key
        )
        return signed_message.signature.hex()
        
    def get_random_headers(self, wallet_address):
        """获取随机UA的请求头"""
        headers = self.headers.copy()
        headers['user-agent'] = random.choice(self.user_agents)
        return headers
        
    async def stop_node(self, session, private_key, proxy):
        """停止节点"""
        try:
            wallet_address = await self.get_wallet_address(private_key)
            headers = self.get_random_headers(wallet_address)
            timestamp = int(time.time() * 1000)
            
            logging.info(f"Stopping node: {wallet_address[:6]}...{wallet_address[-4:]}")
            
            message = f"Node deactivation request for {wallet_address} at {timestamp}"
            signature = await self.sign_message(message, private_key)
            
            if not signature.startswith('0x'):
                signature = f"0x{signature}"
            
            payload = {
                "timestamp": timestamp,
                "sign": signature
            }
            
            stop_data = await self.make_request(
                session,
                'POST',
                f'https://referralapi.layeredge.io/api/light-node/node-action/{wallet_address}/stop',
                proxy,
                headers,
                payload
            )
            
            
            if stop_data.get('message') == 'node action executed successfully':
                logging.info(f"Node stopped successfully")
                return True
            else:
                logging.error(f"Failed to stop node: {stop_data.get('message')}")
                return False
                
        except Exception as e:
            logging.error(f"Error stopping node: {str(e)}")
            return False

    async def check_node_status(self, session, wallet_address, proxy, headers):
        """检查节点状态"""
        status_data = await self.make_request(
            session,
            'GET',
            f'https://referralapi.layeredge.io/api/light-node/node-status/{wallet_address}',
            proxy,
            headers
        )
        
        logging.info(f"Node status: startTimestamp = {status_data.get('data', {}).get('startTimestamp')}")
        return status_data

    async def start_node(self, session, private_key, proxy):
        """启动节点"""
        try:
            wallet_address = await self.get_wallet_address(private_key)
            headers = self.get_random_headers(wallet_address)
            timestamp = int(time.time() * 1000)
            
            logging.info(f"Starting node: {wallet_address[:6]}...{wallet_address[-4:]}")
            
            message = f"Node activation request for {wallet_address} at {timestamp}"
            signature = await self.sign_message(message, private_key)
            
            if not signature.startswith('0x'):
                signature = f"0x{signature}"
            
            payload = {
                "timestamp": timestamp,
                "sign": signature
            }
            
            start_data = await self.make_request(
                session,
                'POST',
                f'https://referralapi.layeredge.io/api/light-node/node-action/{wallet_address}/start',
                proxy,
                headers,
                payload
            )
            
            
            if start_data.get('message') == 'node action executed successfully':
                logging.info(f"Node started successfully")
                return True
            else:
                logging.error(f"Failed to start node: {start_data.get('message')}")
                return False
                
        except Exception as e:
            logging.error(f"Error starting node: {str(e)}")
            return False
            
    async def claim_daily_points(self, session, private_key, proxy):
        """签到领取积分"""
        try:
            wallet_address = await self.get_wallet_address(private_key)
            headers = self.get_random_headers(wallet_address)
            timestamp = int(time.time() * 1000)
            
            message = f"I am claiming my daily node point for {wallet_address} at {timestamp}"
            signature = await self.sign_message(message, private_key)
            
            
            if not signature.startswith('0x'):
                signature = f"0x{signature}"
            
            payload = {
                "walletAddress": wallet_address,
                "timestamp": timestamp,
                "sign": signature
            }
            
            async with session.post(
                'https://referralapi.layeredge.io/api/light-node/claim-node-points',
                json=payload,
                proxy=proxy,
                headers=headers
            ) as resp:
                claim_data = await resp.json()
                
                if resp.status < 400:
                    logging.info(f"Successfully claimed points for {wallet_address}: {claim_data}")
                    return True
                elif resp.status == 405:
                    if 'message' in claim_data and '24 hours' in claim_data['message']:
                        logging.info(f"Check in is already done for {wallet_address}")
                        return True  
                    else:
                        logging.error(f"Failed to perform check in for {wallet_address}")
                        return False
                else:
                    logging.warning(f"Failed to claim points for {wallet_address}, status: {resp.status}, response: {claim_data}")
                    return False
        except Exception as e:
            logging.error(f"Error claiming points for {wallet_address}: {str(e)}")
            return False
            
    async def make_request(self, session, method, url, proxy, headers, json=None):
        """统一的请求处理函数"""
        try:
            for retry in range(self.config['retry_times']):
                try:
                    async with session.request(
                        method=method,
                        url=url,
                        proxy=proxy,
                        headers=headers,
                        json=json,
                        ssl=False,
                        timeout=30
                    ) as resp:
                        
                        if resp.status == 502:
                            logging.warning(f"Bad Gateway error, retrying... ({retry + 1}/{self.config['retry_times']})")
                            await asyncio.sleep(2 ** retry)
                            continue
                        
                        
                        content_type = resp.headers.get('content-type', '')
                        if 'application/json' not in content_type:
                            logging.warning(f"Unexpected content type: {content_type}, retrying...")
                            await asyncio.sleep(2 ** retry)
                            continue
                        
                        return await resp.json()
                    
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    if retry == self.config['retry_times'] - 1:
                        raise
                    logging.warning(f"Request failed, retrying... ({retry + 1}/{self.config['retry_times']}): {str(e)}")
                    await asyncio.sleep(2 ** retry)
                
        except Exception as e:
            logging.error(f"Request failed: {url} - {str(e)}")
            raise

    async def get_wallet_details(self, session, wallet_address, proxy, headers):
        """获取钱包详情，包括节点积分"""
        try:
            details = await self.make_request(
                session,
                'GET',
                f'https://referralapi.layeredge.io/api/referral/wallet-details/{wallet_address}',
                proxy,
                headers
            )
            if 'data' in details and 'nodePoints' in details['data']:
                self.node_points[wallet_address] = details['data']['nodePoints']
                return details['data']['nodePoints']
        except Exception as e:
            logging.error(f"Error getting wallet details: {str(e)}")
        return None

    def format_log(self, wallet_address, message, level="INFO", emoji=None, action_type=None):
        """格式化日志输出"""
        points = self.node_points.get(wallet_address, "Unknown")
        short_address = f"{wallet_address[:6]}...{wallet_address[-4:]}"
        emoji_str = f"{self.emojis.get(emoji, '')} " if emoji else ""
        
        
        color_map = {
            'start': 'green',
            'stop': 'red',
            'claim': 'yellow',
            'status': 'blue',
            'error': 'red',
            'warning': 'yellow'
        }
        
        color = color_map.get(action_type, 'white')
        message_text = Text()
        message_text.append(f"[{level}] ", style="bold")
        message_text.append(f"[{short_address}] ", style="cyan")
        message_text.append(f"[Points: {points}] ", style="magenta")
        message_text.append(f"{emoji_str}{message}", style=color)
        
        return message_text

    async def monitor_account(self, private_key, proxy):
        """监控单个账户"""
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            wallet_address = await self.get_wallet_address(private_key)
            headers = self.get_random_headers(wallet_address)
            last_restart_time = 0
            
            while True:
                try:
                    current_time = time.time()
                    
                    
                    try:
                        points = await self.get_wallet_details(session, wallet_address, proxy, headers)
                        if points is not None:
                            logging.info(self.format_log(wallet_address, f"Current points: {points}", emoji='points', action_type='status'))
                    except Exception as e:
                        logging.error(self.format_log(wallet_address, f"Error getting points: {str(e)}", "ERROR", emoji='error', action_type='error'))
                    
                    
                    if current_time - last_restart_time >= self.config['restart_interval']:
                        logging.info(self.format_log(wallet_address, "Scheduled node restart", emoji='restart', action_type='stop'))
                        
                        try:
                            
                            stop_success = await self.stop_node(session, private_key, proxy)
                            if stop_success:
                                logging.info(self.format_log(wallet_address, "Node stopped for scheduled restart", emoji='stop', action_type='stop'))
                                await asyncio.sleep(5)
                                
                                
                                start_success = await self.start_node(session, private_key, proxy)
                                if start_success:
                                    last_restart_time = current_time
                                    logging.info(self.format_log(wallet_address, "Node restarted successfully", emoji='start', action_type='start'))
                                else:
                                    logging.error(self.format_log(wallet_address, "Failed to restart node", "ERROR", emoji='error', action_type='error'))
                        except Exception as e:
                            logging.error(self.format_log(wallet_address, f"Error during node restart: {str(e)}", "ERROR", emoji='error', action_type='error'))
                    
                    
                    try:
                        claim_success = await self.claim_daily_points(session, private_key, proxy)
                        if claim_success:
                            logging.info(self.format_log(wallet_address, "Daily check-in successful", emoji='check', action_type='claim'))
                            await asyncio.sleep(self.config['claim_success_wait'])
                        else:
                            logging.info(self.format_log(wallet_address, "Check-in failed, will retry", emoji='warning', action_type='warning'))
                            await asyncio.sleep(self.config['claim_fail_wait'])
                    except Exception as e:
                        logging.error(self.format_log(wallet_address, f"Error during check-in: {str(e)}", "ERROR", emoji='error', action_type='error'))
                        await asyncio.sleep(300)
                    
                    await asyncio.sleep(self.config['check_interval'])
                    
                except Exception as e:
                    logging.error(self.format_log(wallet_address, f"Error: {str(e)}", "ERROR", emoji='error', action_type='error'))
                    await asyncio.sleep(60)
                    
    async def run(self):
        """运行主程序"""
        self.print_banner()  
        tasks = []
        for private_key, proxy in zip(self.accounts, self.proxies):
            task = asyncio.create_task(self.monitor_account(private_key, proxy))
            tasks.append(task)
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    bot = LayerEdgeBot()
    asyncio.run(bot.run())
