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
                "log_level": "INFO",
                "max_concurrent_tasks": 5
            }

    def print_banner(self):
        
        banner = f"""[bold cyan]
╔═══════════════════════════════════════════════════════════════╗
║  LAYEREDGE BOT 2.0.0                                          ║
╠═══════════════════════════════════════════════════════════════╣
║  作者: [green]SniffTunes[/green]                                             ║
║  推特: [blue]https://x.com/snifftunes[/blue]                               ║
║  版本: [green]2.0.0[/green]                                                  ║
╚═══════════════════════════════════════════════════════════════╝[/bold cyan]
"""
        console.print(banner)

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
        self.ref_results = {}  
        
    def load_accounts(self):
        
        with open('accounts.txt', 'r') as f:
            return [line.strip() for line in f.readlines()]
            
    def load_proxies(self):
        
        with open('proxy.txt', 'r') as f:
            return [line.strip() for line in f.readlines()]
            
    def load_user_agents(self):
        
        with open('ua.txt', 'r') as f:
            return [line.strip() for line in f.readlines()]
            
    async def get_wallet_address(self, private_key):
        
        account = self.w3.eth.account.from_key(private_key)
        return account.address
        
    async def sign_message(self, message, private_key):
        
        message_hash = encode_defunct(text=message)
        signed_message = self.w3.eth.account.sign_message(
            message_hash,
            private_key=private_key
        )
        return signed_message.signature.hex()
        
    def get_random_headers(self, wallet_address):
        
        headers = self.headers.copy()
        headers['user-agent'] = random.choice(self.user_agents)
        return headers
        
    async def stop_node(self, session, private_key, proxy):
        
        try:
            wallet_address = await self.get_wallet_address(private_key)
            headers = self.get_random_headers(wallet_address)
            timestamp = int(time.time() * 1000)
            
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
                logging.info("Node stopped successfully")
                logging.info(self.format_log(wallet_address, "Node stopped for scheduled restart", emoji='stop', action_type='stop'))
                return True
            else:
                logging.error(self.format_log(wallet_address, f"Failed to stop node: {stop_data.get('message')}", "ERROR", emoji='error', action_type='error'))
                return False
                    
        except Exception as e:
            logging.error(self.format_log(wallet_address, f"Error stopping node: {str(e)}", "ERROR", emoji='error', action_type='error'))
            return False

    async def check_node_status(self, session, wallet_address, proxy, headers):
        
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
                logging.info("Node started successfully")
                logging.info(self.format_log(wallet_address, "Node started successfully", emoji='start', action_type='start'))
                return True
            else:
                logging.error(self.format_log(wallet_address, f"Failed to start node: {start_data.get('message')}", "ERROR", emoji='error', action_type='error'))
                return False
                    
        except Exception as e:
            logging.error(self.format_log(wallet_address, f"Error starting node: {str(e)}", "ERROR", emoji='error', action_type='error'))
            return False
            
    async def claim_daily_points(self, session, private_key, proxy):
        
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

    async def update_node_status_and_points(self, session, wallet_address, proxy, headers):
        
        while True:
            try:
                
                status_data = await self.make_request(
                    session,
                    'GET',
                    f'https://referralapi.layeredge.io/api/light-node/node-status/{wallet_address}',
                    proxy,
                    headers
                )
                
                if status_data and 'data' in status_data:
                    timestamp = status_data['data'].get('startTimestamp')
                    if timestamp:
                        logging.info(f"Node status: startTimestamp = {timestamp}")
                
                
                if int(time.time()) % 60 == 0:
                    details = await self.make_request(
                        session,
                        'GET',
                        f'https://referralapi.layeredge.io/api/referral/wallet-details/{wallet_address}',
                        proxy,
                        headers
                    )
                    
                    if details and 'data' in details and 'nodePoints' in details['data']:
                        new_points = details['data']['nodePoints']
                        old_points = self.node_points.get(wallet_address, 0)
                        self.node_points[wallet_address] = new_points
                        
                        
                        if old_points != new_points:
                            diff = new_points - old_points
                            sign = '+' if diff > 0 else ''
                            logging.info(self.format_log(
                                wallet_address,
                                f"Points: {old_points:,} → {new_points:,} ({sign}{diff:,})",
                                emoji='points',
                                action_type='points'
                            ))
                
                await asyncio.sleep(10)
                
            except Exception as e:
                logging.error(self.format_log(
                    wallet_address,
                    f"Error updating status and points: {str(e)}",
                    "ERROR",
                    emoji='error',
                    action_type='error'
                ))
                await asyncio.sleep(10)

    async def monitor_account(self, private_key, proxy):
        
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            wallet_address = await self.get_wallet_address(private_key)
            headers = self.get_random_headers(wallet_address)
            last_restart_time = time.time()
            
            
            update_task = asyncio.create_task(
                self.update_node_status_and_points(session, wallet_address, proxy, headers)
            )
            
            try:
                while True:
                    try:
                        current_time = time.time()
                        
                        
                        if current_time - last_restart_time >= self.config['restart_interval']:
                            logging.info(f"Scheduled node restart for {wallet_address[:6]}...{wallet_address[-4:]}")
                            
                            
                            logging.info(f"Stopping node: {wallet_address[:6]}...{wallet_address[-4:]}")
                            stop_success = await self.stop_node(session, private_key, proxy)
                            if stop_success:
                                logging.info("Node stopped successfully")
                                logging.info(self.format_log(wallet_address, "Node stopped for scheduled restart", emoji='stop', action_type='stop'))
                                await asyncio.sleep(5)
                                
                                
                                logging.info(f"Starting node: {wallet_address[:6]}...{wallet_address[-4:]}")
                                start_success = await self.start_node(session, private_key, proxy)
                                if start_success:
                                    last_restart_time = current_time
                                    logging.info("Node started successfully")
                                    logging.info(self.format_log(wallet_address, "Node started successfully", emoji='start', action_type='start'))
                                else:
                                    logging.error(self.format_log(wallet_address, "Failed to start node", "ERROR", emoji='error', action_type='error'))
                            else:
                                logging.error(self.format_log(wallet_address, "Failed to stop node", "ERROR", emoji='error', action_type='error'))
                        
                        
                        claim_success = await self.claim_daily_points(session, private_key, proxy)
                        if claim_success:
                            logging.info(self.format_log(wallet_address, "Daily check-in successful", emoji='check', action_type='claim'))
                        
                        await asyncio.sleep(self.config['check_interval'])
                        
                    except Exception as e:
                        logging.error(self.format_log(wallet_address, f"Error: {str(e)}", "ERROR", emoji='error', action_type='error'))
                        await asyncio.sleep(60)
                        
            finally:
                update_task.cancel()
                try:
                    await update_task
                except asyncio.CancelledError:
                    pass

    async def display_points_summary(self):
        
        while True:
            try:
                console.print("\n" + "═" * 60)
                console.print("[bold cyan]🏆 Points Summary[/bold cyan]")
                console.print("═" * 60)
                
                total_points = 0
                for wallet, points in sorted(self.node_points.items()):
                    short_address = f"{wallet[:6]}...{wallet[-4:]}"
                    console.print(f"[cyan]{short_address}[/cyan]: [yellow]{points:,}[/yellow] points")
                    total_points += points
                
                console.print("═" * 60)
                console.print(f"[bold green]Total Points: {total_points:,}[/bold green]")
                console.print("═" * 60 + "\n")
                
                await asyncio.sleep(120)  
                
            except Exception as e:
                logging.error(f"Error displaying points summary: {str(e)}")
                await asyncio.sleep(120)

    async def process_accounts_in_batches(self, all_tasks):
        
        batch_size = self.config.get('max_concurrent_tasks', 5)
        results = []
        
        for i in range(0, len(all_tasks), batch_size):
            batch = all_tasks[i:i + batch_size]
            batch_tasks = [self.process_account(pk, px) for pk, px in batch]
            
            
            batch_results = await asyncio.gather(*batch_tasks)
            results.extend(batch_results)
            
            
            if i + batch_size < len(all_tasks):
                logging.info("[bold blue]Waiting 3 seconds before processing next batch...[/bold blue]")
                await asyncio.sleep(3)
        
        return results

    async def run(self):
        
        self.print_banner()
        
        
        all_tasks = []
        for private_key, proxy in zip(self.accounts, self.proxies):
            all_tasks.append((private_key, proxy))
        
        
        points_display_task = asyncio.create_task(self.display_points_summary())
        
        
        results = await self.process_accounts_in_batches(all_tasks)
        
        
        console.print("\n[bold cyan]Initial Setup Results:[/bold cyan]")
        for wallet_address, success in results:
            status = "[green]✅ Success[/green]" if success else "[red]❌ Failed[/red]"
            console.print(f"[cyan]{wallet_address[:6]}...{wallet_address[-4:]}[/cyan]: {status}")
        
       
        monitor_tasks = []
        for private_key, proxy in all_tasks:
            task = asyncio.create_task(self.monitor_account(private_key, proxy))
            monitor_tasks.append(task)
        
        
        await asyncio.gather(points_display_task, *monitor_tasks)

    async def process_account(self, private_key, proxy):
        
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            wallet_address = await self.get_wallet_address(private_key)
            headers = self.get_random_headers(wallet_address)
            
            try:
                
                points = await self.get_wallet_details(session, wallet_address, proxy, headers)
                if points is not None:
                    logging.info(self.format_log(wallet_address, f"Current points: {points:,}", emoji='points', action_type='status'))
                
                
                status_data = await self.check_node_status(session, wallet_address, proxy, headers)
                if ('data' not in status_data or 
                    'startTimestamp' not in status_data['data'] or 
                    status_data['data']['startTimestamp'] is None):
                    logging.info(self.format_log(wallet_address, "Node not running, starting node", emoji='start', action_type='start'))
                    start_success = await self.start_node(session, private_key, proxy)
                    if not start_success:
                        logging.info(self.format_log(wallet_address, "Start failed, trying stop then start", emoji='warning', action_type='warning'))
                        await self.stop_node(session, private_key, proxy)
                        await asyncio.sleep(5)
                        await self.start_node(session, private_key, proxy)
                
                
                claim_success = await self.claim_daily_points(session, private_key, proxy)
                if claim_success:
                    logging.info(self.format_log(wallet_address, "Daily check-in successful", emoji='check', action_type='claim'))
                
                return wallet_address, True
                
            except Exception as e:
                logging.error(self.format_log(wallet_address, f"Error processing account: {str(e)}", "ERROR", emoji='error', action_type='error'))
                return wallet_address, False

    async def verify_invite_code(self, session, invite_code, proxy, headers):
        
        try:
            payload = {"invite_code": invite_code}
            result = await self.make_request(
                session,
                'POST',
                'https://referralapi.layeredge.io/api/referral/verify-referral-code',
                proxy,
                headers,
                payload
            )
            return result.get('data', {}).get('valid', False)
        except Exception as e:
            logging.error(f"Error verifying invite code: {str(e)}")
            return False

    def load_register_accounts(self):
        
        try:
            with open('register.txt', 'r') as f:
                return [line.strip() for line in f if line.strip() and not line.startswith('#')]
        except FileNotFoundError:
            logging.error("register.txt not found")
            return []

    def save_ref_results(self):
        
        with open('ref_result.txt', 'w') as f:
            for wallet, success in self.ref_results.items():
                status = "Success" if success else "Failed"
                f.write(f"{wallet}: {status}\n")

    async def register_wallet(self, session, wallet_address, invite_code, proxy, headers):
        
        try:
            payload = {"walletAddress": wallet_address}
            for retry in range(3):  
                try:
                    result = await self.make_request(
                        session,
                        'POST',
                        f'https://referralapi.layeredge.io/api/referral/register-wallet/{invite_code}',
                        proxy,
                        headers,
                        payload
                    )
                    
                    if result.get('message') == 'registered wallet address successfully':
                        logging.info(f"钱包 {wallet_address[:6]}...{wallet_address[-4:]} 注册成功")
                        return True
                        
                    
                    if str(result.get('statusCode', '')).startswith('4'):
                        if retry < 2: 
                            logging.warning(f"注册失败 (尝试 {retry + 1}/3)，等待5秒后重试...")
                            await asyncio.sleep(5)
                            continue
                        else:
                            logging.error(f"注册失败，已达到最大重试次数: {result.get('message', '未知错误')}")
                            return False
                            
                    
                    logging.error(f"注册失败: {result.get('message', '未知错误')}")
                    return False
                    
                except Exception as e:
                    if retry < 2:  
                        logging.warning(f"注册请求异常 (尝试 {retry + 1}/3): {str(e)}")
                        await asyncio.sleep(5)
                        continue
                    else:
                        logging.error(f"注册失败，已达到最大重试次数: {str(e)}")
                        return False
                        
            return False
            
        except Exception as e:
            logging.error(f"注册过程发生错误: {str(e)}")
            return False

    async def process_registration(self, private_key, invite_code, proxy):
        
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                wallet_address = await self.get_wallet_address(private_key)
                headers = self.get_random_headers(wallet_address)
                
               
                is_valid = await self.verify_invite_code(session, invite_code, proxy, headers)
                if not is_valid:
                    logging.error(f"邀请码 {invite_code} 无效")
                    self.ref_results[wallet_address] = False
                    return wallet_address, False
                
                
                success = await self.register_wallet(session, wallet_address, invite_code, proxy, headers)
                self.ref_results[wallet_address] = success
                
                status = "[green]成功[/green]" if success else "[red]失败[/red]"
                console.print(f"钱包 [cyan]{wallet_address[:6]}...{wallet_address[-4:]}[/cyan]: {status}")
                
                return wallet_address, success
                
            except Exception as e:
                logging.error(f"注册处理错误: {str(e)}")
                return None, False

    async def register_accounts(self):
        
        accounts = self.load_register_accounts()
        if not accounts:
            console.print("[red]没有找到待注册账户[/red]")
            return

        invite_code = input("请输入邀请码: ").strip()
        if not invite_code:
            console.print("[red]邀请码不能为空[/red]")
            return

        console.print("[cyan]开始处理注册...[/cyan]")
        
        
        batch_size = self.config.get('max_concurrent_tasks', 5)
        for i in range(0, len(accounts), batch_size):
            batch = accounts[i:i + batch_size]
            tasks = []
            
            console.print(f"\n[yellow]正在处理第 {i//batch_size + 1} 批 ({len(batch)} 个账户)[/yellow]")
            
            for private_key in batch:
                proxy = self.proxies[0] if self.proxies else None
                tasks.append(self.process_registration(private_key, invite_code, proxy))
            
            results = await asyncio.gather(*tasks)
            
            
            success_count = sum(1 for _, success in results if success)
            console.print(f"[cyan]本批处理完成: {success_count}/{len(batch)} 成功[/cyan]")
            
            
            if i + batch_size < len(accounts):
                console.print("[yellow]等待10秒处理下一批...[/yellow]")
                await asyncio.sleep(10)

        
        self.save_ref_results()
        console.print("\n[bold cyan]所有注册处理完成，结果已保存到 ref_result.txt[/bold cyan]")
        
        
        total_success = sum(1 for success in self.ref_results.values() if success)
        console.print(f"[bold]总结: {total_success}/{len(accounts)} 成功注册[/bold]")

    async def show_menu(self):
        
        while True:
            self.print_banner()
            console.print("\n[bold cyan]╔═══════════════════════════════════╗[/bold cyan]")
            console.print("[bold cyan]║          LayerEdge Bot 主菜单     ║[/bold cyan]")
            console.print("[bold cyan]╠═══════════════════════════════════╣[/bold cyan]")
            console.print("[bold cyan]║[/bold cyan] [white]1. 签到与运行节点[/white]                 [bold cyan]║[/bold cyan]")
            console.print("[bold cyan]║[/bold cyan] [white]2. 注册新账户[/white]                     [bold cyan]║[/bold cyan]")
            console.print("[bold cyan]║[/bold cyan] [white]3. 退出[/white]                           [bold cyan]║[/bold cyan]")
            console.print("[bold cyan]╚═══════════════════════════════════╝[/bold cyan]")
            
            choice = input("\n请选择功能 (1-3): ").strip()
            
            if choice == "1":
                await self.run_main()
            elif choice == "2":
                await self.register_accounts()
            elif choice == "3":
                console.print("\n[yellow]感谢使用，正在退出程序...[/yellow]")
                break
            else:
                console.print("\n[red]❌ 无效的选择，请重试[/red]")

    async def run_main(self):
        
        self.print_banner()
        
        
        all_tasks = []
        for private_key, proxy in zip(self.accounts, self.proxies):
            all_tasks.append((private_key, proxy))
        
        
        points_display_task = asyncio.create_task(self.display_points_summary())
        
        
        results = await self.process_accounts_in_batches(all_tasks)
        
        
        console.print("\n[bold cyan]初始化结果:[/bold cyan]")
        for wallet_address, success in results:
            status = "[green]✅ 成功[/green]" if success else "[red]❌ 失败[/red]"
            console.print(f"[cyan]{wallet_address[:6]}...{wallet_address[-4:]}[/cyan]: {status}")
        
        
        monitor_tasks = []
        for private_key, proxy in all_tasks:
            task = asyncio.create_task(self.monitor_account(private_key, proxy))
            monitor_tasks.append(task)
        
        
        await asyncio.gather(points_display_task, *monitor_tasks)

if __name__ == "__main__":
    bot = LayerEdgeBot()
    asyncio.run(bot.show_menu())
