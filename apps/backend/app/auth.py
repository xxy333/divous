import os
import time
import json
import secrets
from typing import Any, Dict, Optional, List, Callable

import httpx
from jose import JWTError
from jose.exceptions import JWTError
from fastapi import Request, HTTPE