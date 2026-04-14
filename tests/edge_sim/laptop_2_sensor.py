import asyncio
import random
import logging
from pymodbus.server import StartAsyncTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

logging.basicConfig()
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

async def updating_task(context):
    """Constantly updates the values in the simulated Modbus server."""
    log.info("Starting background Modbus data generator...")
    while True:
        await asyncio.sleep(5)
        # Randomize Voltage (Reg 0) and Power (Reg 1). We multiply by 10 to simulate typical Modbus decimal scaling.
        voltage = int((230.0 + random.uniform(-2, 2)) * 10)
        power = int((450.0 + random.uniform(-10, 10)) * 10)
        
        # Write to holding registers (function code 3, address 0)
        context[0].setValues(3, 0, [voltage, power])
        log.info(f"Modbus Registers Updated: Voltage={voltage/10}V, Power={power/10}W")

async def run_server():
    # Setup Data Store (Holding Registers start at 0)
    store = ModbusSlaveContext(
        di=ModbusSequentialDataBlock(0, [0]*10),
        co=ModbusSequentialDataBlock(0, [0]*10),
        hr=ModbusSequentialDataBlock(0, [0]*10),
        ir=ModbusSequentialDataBlock(0, [0]*10)
    )
    context = ModbusServerContext(slaves=store, single=True)
    
    # Identify the simulated equipment
    identity = ModbusDeviceIdentification()
    identity.VendorName = 'Nodeflow Simulated Equipment'
    identity.ProductCode = 'NF-SIM-S7-MOCK'
    
    # Start the updating task in the background
    asyncio.create_task(updating_task(context))
    
    # Port 5020 is used instead of 502 because ports under 1024 require Administrator/root privileges.
    log.info("Starting Modbus TCP SERVER on port 5020...")
    log.info("Waiting for Modbus Client (Nodeflow Edge) to connect...")
    await StartAsyncTcpServer(
        context=context,
        identity=identity,
        address=("0.0.0.0", 5020)
    )

if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        log.info("Modbus Server Stopped.")
