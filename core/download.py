"""
Módulo para download de vídeos do Google Meet do Google Drive.
Baseado nas técnicas do artigo: 
https://dev.to/gabrieldiem/how-to-download-google-meet-meeting-recordings-set-to-view-only-mode-4d2a
"""

import os
import re
import time
import logging
from pathlib import Path
from typing import Optional

import requests
from tqdm import tqdm
import gdown
import yt_dlp

logger = logging.getLogger("DownMeets.download")


def extract_file_id(url: str) -> str:
    """Extrai o ID do arquivo do Google Drive a partir da URL."""
    pattern = r'/d/([a-zA-Z0-9_-]+)'
    match = re.search(pattern, url)
    
    if match:
        return match.group(1)
    else:
        raise ValueError("Não foi possível extrair o ID do arquivo da URL fornecida.")


def download_with_ytdlp(url: str, output_path: str) -> bool:
    """Baixa vídeo usando yt-dlp."""
    logger.info(f"Tentando baixar com yt-dlp: {url}")
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': output_path,
        'quiet': False,
        'no_warnings': False,
        'ignoreerrors': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        # Verificar se o arquivo foi baixado e tem tamanho
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
        else:
            logger.warning("Arquivo baixado com yt-dlp está vazio ou não existe")
            return False
    except Exception as e:
        logger.error(f"Erro com yt-dlp: {e}")
        return False


def download_with_requests(url: str, output_path: str) -> bool:
    """Tenta baixar usando requests."""
    logger.info(f"Tentando baixar com requests: {url}")
    
    try:
        # Extrair ID
        file_id = extract_file_id(url)
        
        # URL para download direto
        direct_url = f"https://drive.google.com/uc?id={file_id}&export=download"
        
        # Cabeçalhos para emular navegador
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://drive.google.com/',
        }
        
        # Sessão para manter cookies
        session = requests.Session()
        
        # Primeira requisição para obter cookies
        response = session.get(direct_url, headers=headers, stream=True)
        
        # Lidar com página de confirmação
        if 'confirm=' in response.url or 'confirm=' in response.text:
            confirm_match = re.search(r'confirm=([0-9A-Za-z_-]+)', response.url)
            if not confirm_match:
                confirm_match = re.search(r'confirm=([0-9A-Za-z_-]+)', response.text)
            
            if confirm_match:
                confirm_token = confirm_match.group(1)
                direct_url = f"https://drive.google.com/uc?id={file_id}&export=download&confirm={confirm_token}"
                response = session.get(direct_url, headers=headers, stream=True)
        
        # Verificar se recebemos um arquivo ou HTML
        if 'text/html' in response.headers.get('Content-Type', ''):
            # Tentar extrair URL de mídia direta
            media_urls = re.findall(r'https://.*?googleusercontent\.com/[^"\'&?]+', response.text)
            media_urls = [u for u in media_urls if 'videoplayback' in u or 'media' in u]
            
            if media_urls:
                logger.info(f"URL de mídia encontrada: {media_urls[0]}")
                response = session.get(media_urls[0], headers=headers, stream=True)
            else:
                return False
        
        # Obter tamanho do arquivo
        file_size = int(response.headers.get('content-length', 0))
        
        if file_size > 0:
            # Exibir progresso
            progress = tqdm(
                response.iter_content(1024),
                f"Baixando {os.path.basename(output_path)}",
                total=file_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
            )
            
            # Baixar o arquivo
            with open(output_path, 'wb') as f:
                for data in progress.iterable:
                    f.write(data)
                    progress.update(len(data))
        else:
            # Sem content-length, baixar sem progresso
            with open(output_path, 'wb') as f:
                f.write(response.content)
        
        # Verificar se o arquivo baixado tem conteúdo
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
        else:
            logger.warning("Arquivo baixado está vazio")
            return False
    
    except Exception as e:
        logger.error(f"Erro com requests: {e}")
        return False


def download_with_gdown(url: str, output_path: str) -> bool:
    """Tenta baixar usando gdown."""
    logger.info(f"Tentando baixar com gdown: {url}")
    
    try:
        # Extrair ID
        file_id = extract_file_id(url)
        
        # Baixar com gdown
        gdown.download(id=file_id, output=output_path, quiet=False, fuzzy=True)
        
        # Verificar se o arquivo foi baixado com sucesso
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
        else:
            logger.warning("gdown não conseguiu baixar o arquivo ou o arquivo está vazio")
            return False
    except Exception as e:
        logger.error(f"Erro com gdown: {e}")
        return False


def download_meet_video(url: str, output_path: str) -> bool:
    """Baixa um vídeo do Google Meet usando múltiplos métodos."""
    # Garantir que o diretório existe
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    logger.info(f"Baixando para: {output_path}")
    
    # Tentar diferentes métodos de download
    if download_with_ytdlp(url, output_path):
        logger.info("Download bem-sucedido com yt-dlp!")
        return True
    
    logger.info("yt-dlp falhou, tentando método alternativo...")
    
    if download_with_requests(url, output_path):
        logger.info("Download bem-sucedido com requests!")
        return True
    
    logger.info("requests falhou, tentando gdown...")
    
    if download_with_gdown(url, output_path):
        logger.info("Download bem-sucedido com gdown!")
        return True
    
    logger.error("Todos os métodos de download falharam.")
    return False