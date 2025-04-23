"""
Módulo de utilidades para o DownMeets.
"""

import os
import sys
import time
import subprocess
import logging
from typing import List, Optional

logger = logging.getLogger("DownMeets.utils")


def wait_between_items(minutes: int) -> None:
    """Aguarda um tempo especificado entre processamentos."""
    if minutes <= 0:
        return
    
    logger.info(f"Aguardando {minutes} minuto(s) antes do próximo processamento...")
    time.sleep(minutes * 60)


def check_dependencies(need_openai: bool = False, need_ffmpeg: bool = False) -> List[str]:
    """
    Verifica se as dependências necessárias estão instaladas.
    Retorna uma lista com as dependências ausentes.
    """
    missing = []
    
    # Verificar dependências Python
    required_packages = ["requests", "tqdm", "gdown", "yt_dlp"]
    
    if need_openai:
        required_packages.append("openai")
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    # Verificar FFmpeg se necessário
    if need_ffmpeg and not is_ffmpeg_installed():
        missing.append("ffmpeg")
    
    return missing


def is_ffmpeg_installed() -> bool:
    """Verifica se o FFmpeg está instalado."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def install_python_dependencies(missing_packages: List[str]) -> bool:
    """
    Tenta instalar dependências Python ausentes.
    Retorna True se todas as dependências foram instaladas com sucesso.
    """
    if not missing_packages:
        return True
    
    logger.info(f"Tentando instalar dependências ausentes: {', '.join(missing_packages)}")
    
    for package in missing_packages:
        try:
            logger.info(f"Instalando {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        except subprocess.CalledProcessError as e:
            logger.error(f"Falha ao instalar {package}: {e}")
            return False
    
    return True


def format_time(seconds: int) -> str:
    """Formata tempo em segundos para uma string legível."""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    
    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    else:
        return f"{s}s"


def get_file_size_str(path: str) -> str:
    """Retorna o tamanho de um arquivo em formato legível."""
    if not os.path.exists(path):
        return "0 B"
    
    size = os.path.getsize(path)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def get_video_duration(video_path: str) -> Optional[int]:
    """
    Obtém a duração de um vídeo em segundos usando FFmpeg.
    Retorna None se não for possível obter a duração.
    """
    if not os.path.exists(video_path):
        logger.error(f"Vídeo não encontrado: {video_path}")
        return None
    
    try:
        # Comando para obter informações do vídeo usando FFmpeg
        command = [
            "ffprobe", 
            "-v", "error", 
            "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", 
            video_path
        ]
        
        # Executar o comando
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            logger.error(f"Erro ao obter duração do vídeo: {result.stderr}")
            return None
        
        # Converter a saída para um número inteiro de segundos
        try:
            duration = float(result.stdout.strip())
            return int(duration)
        except (ValueError, TypeError) as e:
            logger.error(f"Erro ao converter duração do vídeo: {e}")
            return None
    
    except Exception as e:
        logger.exception(f"Erro ao obter duração do vídeo: {str(e)}")
        return None