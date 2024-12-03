from fastapi import FastAPI
from fastapi import Depends, FastAPI, HTTPException, Query
from mysql.connector.aio import connect
import json
import asyncio

sourcedb = {
  "host":"localhost",
  "user":"root",
  "password":"rootpassword",
  "port":4406,
  "database":"steam",
}

replica1db = {
  "host":"localhost",
  "user":"root",
  "password":"rootpassword",
  "port":5506,
  "database":"steam",
}


replica2db = {
  "host":"localhost",
  "user":"root",
  "password":"rootpassword",
  "port":6606,
  "database":"steam",
}
app = FastAPI()

app.sourceconnection = True
app.replica1connection = True
app.replica2connection = True
app.mastertoslave = False
app.startupcheck = False

async def getconnections():
    if((not app.startupcheck and app.sourceconnection) or (app.mastertoslave and app.sourceconnection)):
        app.startupcheck = True
        sourcecnx = await connect(**sourcedb)
        replica1cnx = await connect(**replica1db)
        replica2cnx = await connect(**replica2db)
        await changemaster(sourcecnx)
        await changetoslave(replica1cnx,["source"])
        await changetoslave(replica2cnx,["source"])  
        if(app.mastertoslave and app.sourceconnection):
            app.mastertoslave = False
    if(app.sourceconnection):
        sourcecnx = await connect(**sourcedb)
    if(app.replica1connection and app.sourceconnection):
        replica1cnx = await connect(**replica1db)
    if(app.replica2connection and app.sourceconnection):
        replica2cnx = await connect(**replica2db)
    if(not app.replica1connection and app.sourceconnection):
        replica1cnx = await connect(**sourcedb)
    if(not app.replica2connection and app.sourceconnection):
        replica2cnx = await connect(**sourcedb)
    if(not app.sourceconnection and app.replica1connection and not app.mastertoslave):
        app.mastertoslave = True
        sourcecnx = await connect(**sourcedb)
        replica1cnx = await connect(**replica1db)
        replica2cnx = await connect(**replica2db)
        await changemaster(replica1cnx)
        await changetoslave(sourcecnx,["replica1"])
        await changetoslave(replica2cnx,["replica1"])
        sourcecnx = await connect(**replica1db)
        if(not app.replica2connection):
            replica2cnx = await connect(**replica1db)
    if(not app.sourceconnection and app.replica1connection and app.mastertoslave):
        sourcecnx = await connect(**replica1db)
        replica1cnx = await connect(**replica1db)
        replica2cnx = await connect(**replica2db)       
        if(not app.replica2connection):
            replica2cnx = await connect(**replica1db) 
    if(not app.sourceconnection and not app.replica1connection and not app.mastertoslave):
        app.mastertoslave = True
        sourcecnx = await connect(**sourcedb)
        replica1cnx = await connect(**replica1db)
        replica2cnx = await connect(**replica2db)
        await changemaster(replica2cnx)
        await changetoslave(sourcecnx,["replica2"])
        await changetoslave(replica1cnx,["replica2"])
        sourcecnx = await connect(**replica2db)
        if(not app.replica1connection):
            replica1cnx = await connect(**replica2db)
    if(not app.sourceconnection and not app.replica1connection and app.mastertoslave):
        sourcecnx = await connect(**replica2db)
        replica1cnx = await connect(**replica2db)
        replica2cnx = await connect(**replica2db)       
    return sourcecnx, replica1cnx, replica2cnx

async def changemaster(connection):
    cursor = await connection.cursor()
    await cursor.execute("""STOP SLAVE;""")
    await cursor.execute("""RESET MASTER;""")
    return await cursor.fetchall()

async def changetoslave(connection, host):
    cursor = await connection.cursor()
    await cursor.execute("""STOP SLAVE;""")
    await cursor.execute("""
                    CHANGE MASTER TO
                    MASTER_HOST=%s,
                    MASTER_USER='stadvdb',
                    MASTER_PASSWORD='stadvdb';
                    """, host)
    await cursor.execute("""START SLAVE;""")
    return await cursor.fetchall()



@app.get("/")
async def root():
    return {"hello world"}

@app.get("/read")
async def read_database(id: int | None = None):

    sourcecnx, replica1cnx, replica2cnx = await getconnections()
    async with(await sourcecnx.cursor() as sourcecursor,
                        await replica1cnx.cursor() as replica1cursor,
                        await replica2cnx.cursor() as replica2cursor):

        sleepmaster =  sourcecursor.execute("DO SLEEP(2);")
        sleepreplica1 =  replica1cursor.execute("DO SLEEP(2);")
        sleepreplica2 =  replica2cursor.execute("DO SLEEP(2);")
        await asyncio.gather(sleepmaster, sleepreplica1, sleepreplica2)

        query = ("SELECT id,name,price FROM Game_Fact_Table ")
        if isinstance(id, int):
            query+="WHERE id="+str(id)+" AND YEAR(releaseDate) < 2019"
        else:
            query+="WHERE YEAR(releaseDate) < 2019"
        replica1 = replica1cursor.execute(query)
        query = ("SELECT id,name,price FROM Game_Fact_Table ")

        if isinstance(id, int):
            query+="WHERE id="+str(id)+" AND YEAR(releaseDate) >= 2019 AND YEAR (releaseDate) <=2022"
        else:
            query+="WHERE YEAR(releaseDate) >= 2019 AND YEAR (releaseDate) <=2022"
        source = sourcecursor.execute(query)
        query = ("SELECT id,name,price FROM Game_Fact_Table ")

        if isinstance(id, int):
            query+="WHERE id="+str(id)+" AND YEAR(releaseDate) > 2022"
        else:
            query+="WHERE YEAR(releaseDate) > 2022"
        replica2 = replica2cursor.execute(query)

        await asyncio.gather(replica1, source, replica2)


        data = await asyncio.gather(replica1cursor.fetchall(), sourcecursor.fetchall(), replica2cursor.fetchall())

        ret = []
        for (id, name, price) in data[0]:
            ret.append({"id":id, "name":name, "price":price})
        for (id, name, price) in data[1]:
            ret.append({"id":id, "name":name, "price":price})
        for (id, name, price) in data[2]:
            ret.append({"id":id, "name":name, "price":price})
        json_string = json.dumps(ret)
        return {json_string}

@app.get("/update")
async def update_record(id: int, price: int):
    sourcecnx, replica1cnx, replica2cnx = await getconnections()
    async with await sourcecnx.cursor() as sourcecursor:
        updatequery = ("UPDATE Game_Fact_Table SET price="+str(price)+" WHERE id="+str(id))
        first = await sourcecursor.execute(updatequery)
        second = await sourcecursor.execute("DO SLEEP(2);")
        commit = await sourcecnx.commit()
        query = ("SELECT id,name,price FROM Game_Fact_Table WHERE id="+str(id))
        third = await sourcecursor.execute(query)

        data = await sourcecursor.fetchall()
        ret = []
        for (id, name, price) in data:
            ret.append({"id":id, "name":name, "price":price})
        json_string = json.dumps(ret)
        return {json_string}

@app.get("/delete")
async def delete_record(id: int):
    sourcecnx, replica1cnx, replica2cnx = await getconnections()
    async with await sourcecnx.cursor() as sourcecursor:
        query = ("SELECT id,name,price FROM Game_Fact_Table WHERE id="+str(id))
        third = await sourcecursor.execute(query)
        data = await sourcecursor.fetchall()
        deletequery = ("DELETE FROM Game_Fact_Table WHERE id="+str(id))
        first = await sourcecursor.execute(deletequery)
        second = await sourcecursor.execute("DO SLEEP(2);")
        commit = await sourcecnx.commit()

        ret = []
        for (id, name, price) in data:
            ret.append({"id":id, "name":name, "price":price})
        json_string = json.dumps(ret)
        return {json_string}

@app.get("/insert")
async def insert_record(id: int, name: str, price: float, date: str = "1997-06-30"):
    sourcecnx, replica1cnx, replica2cnx = await getconnections()
    async with await sourcecnx.cursor() as sourcecursor:
        insertquery = """INSERT INTO Game_Fact_Table (id,name,price,about,detailedDesc,shortDesc,releaseDate) VALUES (%s,%s,%s,'','','',%s);"""
        first = await sourcecursor.execute(insertquery,(id,name,price,date))
        third = await sourcecursor.execute("DO SLEEP(2);")
        commit = await sourcecnx.commit()
        query = ("SELECT id,name,price FROM Game_Fact_Table WHERE id="+str(id))
        second = await sourcecursor.execute(query)
        data = await sourcecursor.fetchall()

        ret = []
        for (id, name, price) in data:
            ret.append({"id":id, "name":name, "price":price})
        json_string = json.dumps(ret)
        return {json_string}

@app.get("/master")
async def setconnection(conn: bool):
    app.sourceconnection = conn
    return{"Connection Status":app.sourceconnection}

@app.get("/slave1")
async def setconnection(conn: bool):
    app.replica1connection = conn
    return{"Connection Status":app.replica1connection}

@app.get("/slave2")
async def setconnection(conn: bool):
    app.replica2connection = conn
    return{"Connection Status":app.replica1connection}

