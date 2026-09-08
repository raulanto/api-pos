#!/bin/sh
# Bootstrap de LocalStack: se ejecuta solo cuando LocalStack está listo.
#   - crea el bucket de imágenes (+ CORS)
#   - despliega la Lambda de miniaturas (zip generado por el servicio `lambda_build`)
#   - conecta el evento S3 `ObjectCreated` (prefijo originales/) -> Lambda
set -e

BUCKET="${S3_BUCKET_IMAGENES:-pos-imagenes}"
FN=pos-thumbnailer
ZIP=/opt/code/lambda-dist/function.zip
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
ACCOUNT=000000000000
FN_ARN="arn:aws:lambda:${REGION}:${ACCOUNT}:function:${FN}"

echo "[init] bucket s3://$BUCKET"
awslocal s3 mb "s3://$BUCKET" 2>/dev/null || true
awslocal s3api put-bucket-cors --bucket "$BUCKET" --cors-configuration '{
  "CORSRules": [{
    "AllowedMethods": ["GET", "PUT", "HEAD"],
    "AllowedOrigins": ["*"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag"]
  }]
}'

if [ ! -f "$ZIP" ]; then
  # La Lambda de miniaturas es opcional: sin el zip (lambda_build no corrió o
  # falló el pip install), el bucket + CORS ya quedaron listos y la API funciona
  # igual. Se salta el deploy de la Lambda en vez de tumbar todo el init.
  echo "[init] AVISO: no hay $ZIP; se omite la Lambda de miniaturas." >&2
  echo "[init] listo (sin Lambda)."
  exit 0
fi

# Idempotente: con PERSISTENCE=1 la función ya existe en el 2º arranque.
if awslocal lambda get-function --function-name "$FN" >/dev/null 2>&1; then
  echo "[init] lambda $FN ya existe (estado persistido); no se recrea."
else
  echo "[init] lambda $FN"
  awslocal lambda create-function \
    --function-name "$FN" \
    --runtime python3.12 \
    --handler handler.handler \
    --timeout 60 \
    --memory-size 512 \
    --role "arn:aws:iam::${ACCOUNT}:role/lambda-role" \
    --zip-file "fileb://$ZIP" >/dev/null
  awslocal lambda wait function-active-v2 --function-name "$FN"

  awslocal lambda add-permission \
    --function-name "$FN" \
    --statement-id s3invoke \
    --action lambda:InvokeFunction \
    --principal s3.amazonaws.com \
    --source-arn "arn:aws:s3:::$BUCKET" >/dev/null
fi

echo "[init] notificación S3 ObjectCreated (originales/) -> $FN"
awslocal s3api put-bucket-notification-configuration \
  --bucket "$BUCKET" \
  --notification-configuration "{
    \"LambdaFunctionConfigurations\": [{
      \"LambdaFunctionArn\": \"$FN_ARN\",
      \"Events\": [\"s3:ObjectCreated:*\"],
      \"Filter\": {\"Key\": {\"FilterRules\": [{\"Name\": \"prefix\", \"Value\": \"originales/\"}]}}
    }]
  }"

echo "[init] listo."
