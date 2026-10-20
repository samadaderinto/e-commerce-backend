FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 HF_HOME=/models TOKENIZERS_PARALLELISM=false
COPY vision/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade 'pip>=25.2,<27' \
    && pip install --no-cache-dir --timeout 120 --retries 5 --resume-retries 10 'torch>=2.6,<3' --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --timeout 120 --retries 5 --resume-retries 10 -r requirements.txt \
    && useradd --uid 10001 --create-home vision \
    && mkdir /models && chown vision /models
COPY product/visual_labels.py ./visual_labels.py
COPY vision/service.py ./service.py
USER vision
CMD ["python", "service.py"]
