*[Versão em Português](README_PTBR.md)*

# DownMeets

Tool for automatic download of Google Meet meeting videos stored on Google Drive.

## Overview

This project allows downloading Google Meet videos that have been shared on Google Drive, even when configured as "view only" and without a direct download option.

## Technique Used

This script is based on the technique described in the article:
[How to download Google Meet meeting recordings set to "view only" mode](https://dev.to/gabrieldiem/how-to-download-google-meet-meeting-recordings-set-to-view-only-mode-4d2a) by Gabriel Diem.

The technique consists of:

1. **Bypassing viewing restrictions**: When Google Drive restricts the download of a video, it still needs to provide streaming for viewing. This script takes advantage of this need to extract the content.

2. **Multiple extraction approaches**:
   - **yt-dlp Method**: Uses the specialized yt-dlp extractor that can extract the video stream directly
   - **Direct URL Method**: Searches for the media stream URL in the HTML code of the page
   - **API Method**: Uses undocumented Google Drive API access points

3. **Browser simulation**: Uses specific HTTP headers to simulate a real browser, bypassing automation restrictions

4. **Redirect handling**: Deals with confirmation pages and warnings that normally prevent automatic downloads

## Requirements

- Python 3.8 or higher
- Dependencies (installed automatically):
  - requests
  - tqdm
  - gdown
  - yt-dlp

## Simple Usage

### To download a single URL:

```bash
python download_meet.py https://drive.google.com/file/d/YOUR_FILE_ID/view
```

### To download multiple URLs:

1. Add the URLs to the `urls.txt` file (one per line)
2. Execute:

```bash
python download_meet.py
```

## Configuration

The main settings are defined at the beginning of the `download_meet.py` file:

```python
# Configuration
URL_FILE = "urls.txt"  # File with URLs
OUTPUT_DIR = "meets"   # Output directory
DELAY_MINUTES = 5      # Delay between downloads in minutes
```

## Features

- **Multiple download methods**: Tries different techniques to ensure download success
- **Configurable delay**: Waits 5 minutes between downloads when there are multiple files
- **Progress bar**: Visual tracking of download progress
- **Automatic dependency installation**: Checks and installs required packages
- **Robust error handling**: If one method fails, others are tried

## How It Works

The script uses three different methods to try to download videos:

1. **yt-dlp**: Specialized library for extracting videos from various platforms
2. **requests**: Direct download using techniques to bypass restrictions
3. **gdown**: Library specific for Google Drive downloads

If one method fails, the next is automatically tried.

## Why It Works

The technique works because Google Drive needs to deliver the video content to the browser for playback, even when the download option is disabled. Specialized libraries like yt-dlp are able to:

1. Identify the streaming endpoints that the browser player uses
2. Extract the necessary authentication cookies and tokens
3. Make requests directly to these endpoints
4. Save the received video stream locally

This method works even when Google Drive shows the message "Download options disabled" or "Download unavailable", since these restrictions are applied at the user interface level, not at the network level where the script operates.

## Troubleshooting

- **Empty file**: The script will automatically try alternative methods
- **Incorrect URLs**: Make sure the URL contains the file ID (`/d/FILE_ID`)
- **Failure in all methods**: Check if the file exists and if you have permission to view it