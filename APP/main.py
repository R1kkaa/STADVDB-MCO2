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


@app.get("/")
async def root():
    return {"hello world"}

@app.get("/read")
async def read_database(id: int | None = None):
    async with(await connect(**sourcedb) as sourcecnx,
                await connect(**replica1db) as replica1cnx,
                await connect(**replica2db) as replica2cnx):
        async with(await sourcecnx.cursor() as sourcecursor,
                            await replica1cnx.cursor() as replica1cursor,
                            await replica2cnx.cursor() as replica2cursor):

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
            json_string = json.dumps(data)

            #sleepmaster = await sourcecursor.execute("DO SLEEP(2);")
            #sleepreplica1 = await replica1cursor.execute("DO SLEEP(2);")
            #sleepreplica2 = await replica2cursor.execute("DO SLEEP(2);")
            #await asyncio.gather(sleepmaster, sleepreplica1, sleepreplica2)

            json_string = json.dumps(ret)
            sourcecnx.close()
            replica1cnx.close()
            replica2cnx.close()
            return {json_string}

@app.get("/update")
async def read_database(id: int, price: int):
    async with await connect(**sourcedb) as sourcecnx:
        async with await sourcecnx.cursor() as sourcecursor:
            updatequery = ("UPDATE Game_Fact_Table SET price="+str(price)+" WHERE id="+str(id))
            first = await sourcecursor.execute(updatequery)
            second = await sourcecursor.execute("DO SLEEP(2);")
            commit = await sourcecnx.commit()
            query = ("SELECT id,name,price FROM Game_Fact_Table WHERE id="+str(id))
            third = await sourcecursor.execute(query)

            data = await sourcecursor.fetchall()
            for (id, name, price) in data[0]:
                ret.append({"id":id, "name":name, "price":price})
            json_string = json.dumps(ret)
            sourcecnx.close()
            return {json_string}