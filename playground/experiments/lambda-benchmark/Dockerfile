FROM public.ecr.aws/lambda/python:3.12
RUN pip install --no-cache-dir numpy==1.26.4 onnxruntime==1.31.1
COPY bench.py ${LAMBDA_TASK_ROOT}/
COPY models/ ${LAMBDA_TASK_ROOT}/models/
CMD ["bench.handler"]
