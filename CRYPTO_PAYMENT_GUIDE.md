# SRPK Pro - Guía de Pagos con Criptomonedas

## 🚀 Resumen

SRPK Pro ahora acepta pagos en criptomonedas a través de Binance Smart Chain (BSC). Los usuarios pueden pagar con:
- **BNB** (Token nativo de BSC)
- **USDT** (Tether USD en BSC)
- **ETH** (Ethereum envuelto en BSC)

Dirección de pago: `0x680c48F49187a2121a25e3F834585a8b82DfdC16`

## 📋 Componentes del Sistema

### 1. Smart Contract (`contracts/SRPKPayment.sol`)
- Maneja los pagos en BNB, USDT y ETH
- Genera y gestiona licencias on-chain
- Eventos para tracking de pagos
- Funciones administrativas para el owner

### 2. API de Pagos Crypto (`crypto_payment_api.py`)
- Verifica transacciones en la blockchain
- Genera tokens JWT para licencias
- Calcula montos según precios actuales
- API REST para integración

### 3. Landing Page con Web3 (`landing/crypto-index.html`)
- Integración con MetaMask y otros wallets
- Selector de tokens de pago
- Verificación de transacciones en tiempo real
- UX optimizada para pagos crypto

## 🛠️ Instalación y Despliegue

### Requisitos Previos
- Node.js 16+ (para el smart contract)
- Docker y Docker Compose
- Cuenta en BSC con BNB para gas
- (Opcional) API key de BscScan para verificación

### Paso 1: Configurar Variables de Entorno

Crea un archivo `.env` en la raíz:

```bash
# Flask Configuration
FLASK_ENV=production
SECRET_KEY=your-secret-key
JWT_SECRET=your-jwt-secret

# Blockchain Configuration
BSC_RPC_URL=https://bsc-dataseed.binance.org/
CONTRACT_ADDRESS=  # Se llenará después del deploy
CONTRACT_ABI=      # Se llenará después del deploy

# Database Configuration
DATABASE_URL=postgresql://user:pass@postgres:5432/srpk_licenses

# CORS Configuration
ALLOWED_ORIGINS=http://localhost,https://yourdomain.com
```

### Paso 2: Desplegar el Smart Contract

```bash
cd contracts
npm install

# Crear .env para el contrato
cat > .env << EOF
PRIVATE_KEY=your-deployer-private-key
BSC_RPC_URL=https://bsc-dataseed.binance.org/
BSCSCAN_API_KEY=your-bscscan-api-key
EOF

# Compilar y testear
npx hardhat compile
npx hardhat test

# Desplegar a BSC Testnet
npx hardhat run scripts/deploy.js --network bscTestnet

# O desplegar a BSC Mainnet
npx hardhat run scripts/deploy.js --network bsc
```

### Paso 3: Actualizar Configuración

Después del despliegue, actualiza el `.env` principal con:
1. `CONTRACT_ADDRESS` desde `deployments/[network]-deployment.json`
2. `CONTRACT_ABI` desde `artifacts/contracts/SRPKPayment.sol/SRPKPayment.json`

### Paso 4: Iniciar el Sistema

```bash
# Detener el sistema antiguo de Stripe
docker-compose down

# Iniciar el sistema de pagos crypto
docker-compose -f docker-compose.crypto.yml up -d
```

O usa el script automatizado:

```bash
./deploy-crypto.sh
```

## 💳 Flujo de Pago

1. **Usuario selecciona plan**: Starter ($99) o Professional ($299)
2. **Elige token de pago**: BNB, USDT o ETH
3. **Conecta wallet**: MetaMask u otro wallet compatible
4. **Envía transacción**: A la dirección de pago
5. **Verificación**: El sistema verifica la transacción on-chain
6. **Licencia generada**: JWT token con 30 días de validez
7. **Email de confirmación**: Con detalles de la licencia

## 🔧 Administración

### Verificar Estado del Sistema

```bash
# Ver logs
docker-compose -f docker-compose.crypto.yml logs -f

# Estado de servicios
docker-compose -f docker-compose.crypto.yml ps

# Health check
curl http://localhost:5001/health
```

### Funciones del Smart Contract

El owner del contrato puede:
- Actualizar la dirección de recepción de pagos
- Revocar licencias
- Retirar fondos de emergencia

Usar Hardhat console o BscScan para interactuar.

### Base de Datos

Las transacciones y licencias se almacenan en PostgreSQL:

```sql
-- Ver pagos recientes
SELECT * FROM crypto_payments ORDER BY created_at DESC LIMIT 10;

-- Ver licencias activas
SELECT * FROM licenses WHERE expiry_time > NOW();
```

## 🚨 Seguridad

1. **Private Keys**: Nunca commities las private keys
2. **Contract Ownership**: Usa una wallet segura (hardware wallet recomendado)
3. **Validación**: Siempre verifica transacciones on-chain
4. **Monitoreo**: Configura alertas para transacciones grandes

## 📊 Monitoreo y Analytics

### Dashboards Recomendados
- BscScan: Para tracking de transacciones
- Dune Analytics: Para métricas de uso
- Grafana + Prometheus: Para monitoreo del sistema

### Métricas Clave
- Total de pagos por token
- Volumen en USD
- Licencias activas
- Tasa de conversión

## 🆘 Troubleshooting

### El usuario no puede conectar wallet
- Verificar que esté en la red BSC
- Limpiar caché del navegador
- Probar con otro wallet

### Transacción no se verifica
- Esperar más confirmaciones (mínimo 3)
- Verificar en BscScan
- Revisar logs del API

### Error de gas insuficiente
- Para BNB: Necesita BNB extra para gas
- Para tokens: Necesita BNB para pagar el gas

## 📝 Scripts Útiles

### Verificar balance del contrato
```javascript
// En Hardhat console
const contract = await ethers.getContractAt("SRPKPayment", CONTRACT_ADDRESS);
const balance = await ethers.provider.getBalance(contract.address);
console.log("Balance:", ethers.utils.formatEther(balance), "BNB");
```

### Generar reporte de ventas
```python
# Script Python para generar reporte
import requests
import json

def generate_sales_report():
    # Implementar lógica de reporte
    pass
```

## 🔄 Actualizaciones Futuras

- [ ] Soporte para más tokens (BUSD, etc.)
- [ ] Integración con oráculos de precios
- [ ] Sistema de referidos on-chain
- [ ] NFTs como licencias
- [ ] Multi-chain support (Polygon, Arbitrum)

## 📞 Soporte

- Email: crypto-support@srpk.io
- Telegram: @srpk_crypto
- Discord: discord.gg/srpk

---

**Nota**: Este sistema está en producción. Siempre haz pruebas en testnet antes de mainnet.