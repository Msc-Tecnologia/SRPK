# SRPK Pro - Sistema Completo de Pagos con Criptomonedas

## 🚀 Resumen del Sistema

El sistema de pagos con criptomonedas de SRPK Pro está ahora completamente implementado con:

- ✅ **Smart Contracts**: Pagos y Webhooks en Binance Smart Chain
- ✅ **API Backend**: Verificación de pagos, precios en tiempo real, emails reales
- ✅ **Sistema de Webhooks**: Notificaciones on-chain y off-chain
- ✅ **Base de Datos**: PostgreSQL con schema completo
- ✅ **Frontend Web3**: Integración con MetaMask y wallets

## 📦 Componentes Implementados

### 1. Smart Contracts

#### SRPKPayment.sol
- Acepta pagos en BNB, USDT y ETH
- Genera licencias on-chain
- Integración con sistema de webhooks
- Eventos para tracking de pagos

#### SRPKWebhooks.sol
- Sistema de webhooks descentralizado
- Suscripción a eventos específicos
- Fee anti-spam configurable
- Gestión de múltiples webhooks por usuario

### 2. Backend API (crypto_payment_api.py)

#### Funciones Reales Implementadas:
- **Obtención de Precios**: Integración con CoinGecko y Binance API
- **Envío de Emails**: SMTP real con templates HTML profesionales
- **Verificación de Tokens**: Decodificación de eventos Transfer ERC20
- **Cache Redis**: Para precios y transacciones procesadas
- **Base de Datos**: Guardado completo de pagos y licencias

#### Endpoints:
- `/api/crypto/payment-info` - Info de pagos con precios actuales
- `/api/crypto/calculate-amount` - Cálculo dinámico de montos
- `/api/crypto/verify-payment` - Verificación completa de transacciones
- `/api/crypto/webhook/register` - Registro de webhooks
- `/api/crypto/prices/history` - Histórico de precios
- `/api/licenses/verify` - Verificación de licencias JWT

### 3. Procesador de Webhooks (webhook_processor.py)

- Monitoreo de eventos blockchain en tiempo real
- Cola de procesamiento con reintentos
- Firma HMAC para seguridad
- Logging completo en base de datos
- Decodificación de eventos específicos

### 4. Base de Datos (schema_crypto.sql)

#### Tablas:
- `crypto_payments` - Pagos realizados
- `licenses` - Licencias generadas
- `token_prices` - Histórico de precios
- `webhook_registrations` - Webhooks registrados
- `webhook_logs` - Logs de entregas
- `api_usage` - Uso de API
- `blockchain_sync` - Estado de sincronización
- `failed_transactions` - Soporte

#### Funciones SQL:
- `validate_license()` - Validación con contador
- `get_license_stats()` - Estadísticas por usuario

### 5. Frontend (crypto-index.html)

- Web3Modal para conexión de wallets
- Selector de tokens visual
- Cálculo de precios en tiempo real
- Verificación de transacciones
- UX optimizada para pagos crypto

## 🛠️ Instalación Completa

### 1. Configurar Entorno

```bash
# Copiar y editar archivo de entorno
cp .env.example .env
nano .env

# Configuraciones requeridas:
# - SMTP_USER y SMTP_PASS para emails
# - DATABASE_URL para PostgreSQL
# - BSC_RPC_URL (opcional, tiene default)
```

### 2. Inicializar Base de Datos

```bash
# Asegurarse de que PostgreSQL esté corriendo
docker-compose -f docker-compose.crypto.yml up -d postgres

# Esperar a que inicie
sleep 10

# Inicializar schema
python init_db.py
```

### 3. Desplegar Smart Contracts

```bash
cd contracts
npm install

# Configurar deployer
cat > .env << EOF
PRIVATE_KEY=tu-private-key-sin-0x
BSC_RPC_URL=https://bsc-dataseed.binance.org/
BSCSCAN_API_KEY=tu-api-key
EOF

# Compilar contratos
npx hardhat compile

# Ejecutar tests
npx hardhat test

# Desplegar a testnet
npx hardhat run scripts/deploy-all.js --network bscTestnet

# O a mainnet
npx hardhat run scripts/deploy-all.js --network bsc
```

### 4. Actualizar Configuración

Después del despliegue, actualizar `.env` con:

```bash
# Desde contracts/deployments/[network]-deployment.json
CONTRACT_ADDRESS=0x...
WEBHOOK_CONTRACT_ADDRESS=0x...

# Desde contracts/deployments/[network]-abis.json
CONTRACT_ABI='[...]'  # Copiar el ABI de payment
```

### 5. Iniciar Sistema

```bash
# Build e iniciar todos los servicios
docker-compose -f docker-compose.crypto.yml up -d

# Verificar que todo esté corriendo
docker-compose -f docker-compose.crypto.yml ps

# Ver logs
docker-compose -f docker-compose.crypto.yml logs -f
```

### 6. Iniciar Procesador de Webhooks

```bash
# En un contenedor separado o como servicio
python webhook_processor.py
```

## 🔧 Configuración de Email

Para envío real de emails, configurar en `.env`:

### Opción 1: Gmail
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASS=tu-contraseña-de-aplicación
```

### Opción 2: SendGrid
```
SENDGRID_API_KEY=tu-api-key
EMAIL_FROM=noreply@tudominio.com
```

## 📊 Monitoreo

### Ver Estadísticas de Pagos
```sql
-- Conectar a PostgreSQL
psql -U srpk -d srpk_licenses

-- Ver pagos recientes
SELECT * FROM payment_stats ORDER BY day DESC LIMIT 7;

-- Ver licencias activas
SELECT * FROM active_licenses;

-- Ver performance de webhooks
SELECT * FROM webhook_performance;
```

### Monitorear Blockchain
```bash
# Ver último bloque procesado
redis-cli get last_processed_block

# Ver precios en cache
redis-cli get price:BNB
redis-cli get price:ETH
redis-cli get price:USDT
```

## 🧪 Testing

### Test Manual de Pago

1. Visitar http://localhost
2. Seleccionar plan (Starter o Professional)
3. Conectar MetaMask
4. Cambiar a BSC Network
5. Seleccionar token (BNB/USDT/ETH)
6. Enviar transacción
7. Verificar pago
8. Revisar email con licencia

### Test de Webhooks

```bash
# Registrar webhook de prueba
curl -X POST http://localhost:5001/api/crypto/webhook/register \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://webhook.site/tu-url-unica",
    "events": ["payment.confirmed", "license.created"]
  }'

# Hacer un pago para trigger el webhook
```

## 🔒 Seguridad

1. **Smart Contracts**:
   - Ownership protegido
   - ReentrancyGuard en pagos
   - Validaciones estrictas

2. **Backend**:
   - Verificación on-chain de todas las transacciones
   - Rate limiting en API
   - CORS configurado
   - JWT para licencias

3. **Webhooks**:
   - Firma HMAC en cada request
   - Fee anti-spam
   - Límite por usuario

4. **Base de Datos**:
   - Conexiones SSL
   - Prepared statements
   - Backups automáticos

## 📈 Métricas y KPIs

El sistema trackea automáticamente:
- Total de pagos por token
- Volumen en USD
- Licencias activas/expiradas
- Performance de webhooks
- Uso de API por licencia
- Tasas de conversión

## 🆘 Troubleshooting

### Problema: "Transaction not found"
**Solución**: Esperar más confirmaciones (mínimo 3 bloques)

### Problema: Email no llega
**Solución**: Verificar configuración SMTP y logs:
```bash
docker-compose -f docker-compose.crypto.yml logs crypto-payment-api | grep "email"
```

### Problema: Webhook no se ejecuta
**Solución**: Verificar que webhook_processor.py esté corriendo y revisar logs

### Problema: Precios no se actualizan
**Solución**: Verificar conexión a APIs externas:
```bash
curl https://api.coingecko.com/api/v3/simple/price?ids=binancecoin,ethereum,tether&vs_currencies=usd
```

## 🚀 Próximos Pasos

1. **Configurar Monitoring**:
   - Grafana para métricas
   - Alertas de transacciones grandes
   - Dashboard de ventas

2. **Optimizaciones**:
   - CDN para assets
   - Load balancer
   - Caché distribuido

3. **Características Adicionales**:
   - Soporte multi-chain
   - Pagos recurrentes on-chain
   - NFTs como prueba de licencia

## 📞 Soporte

- **Documentación**: https://docs.srpk.io
- **Email**: support@srpk.io
- **GitHub Issues**: https://github.com/srpkio/srpk-pro/issues

---

**¡El sistema está completamente funcional y listo para producción!** 🎉

Todos los placeholders han sido reemplazados con implementaciones reales:
- ✅ Precios en tiempo real desde APIs
- ✅ Emails con SMTP real
- ✅ Webhooks funcionales
- ✅ Base de datos completa
- ✅ Smart contracts desplegables