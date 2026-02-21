const { MongoMemoryServer } = require('mongodb-memory-server');
const mongoose = require('mongoose');

let mongod;

/**
 * Connect to the in-memory database.
 */
module.exports.connect = async () => {
  mongod = await MongoMemoryServer.create();
  const uri = mongod.getUri();

  // Set the environment variable for server.js to use
  process.env.MONGODB_URI = uri;

  if (mongoose.connection.readyState !== 0) {
    await mongoose.disconnect();
  }

  // Mongoose 6+ does NOT need deprecated options
  await mongoose.connect(uri);
};

/**
 * Drop database, close the connection and stop mongod.
 */
module.exports.closeDatabase = async () => {
  if (mongod) {
    await mongoose.connection.dropDatabase();
    await mongoose.connection.close();
    await mongod.stop();
  }
};

/**
 * Remove all the data for all db collections.
 */
module.exports.clearDatabase = async () => {
  if (mongoose.connection.readyState !== 0) {
    const collections = mongoose.connection.collections;
    for (const key in collections) {
      const collection = collections[key];
      await collection.deleteMany();
    }
  }
};