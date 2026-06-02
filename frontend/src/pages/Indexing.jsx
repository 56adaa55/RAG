// src/pages/Indexing.jsx
import React, { useState, useEffect } from 'react';
import RandomImage from '../components/RandomImage';
import { apiBaseUrl } from '../config/config';

const Indexing = () => {
  const [embeddingFile, setEmbeddingFile] = useState('');
  //const [vectorDb, setVectorDb] = useState('milvus');
  const [vectorDb, setVectorDb] = useState('chroma');
  const [indexMode, setIndexMode] = useState('standard');
  const [status, setStatus] = useState('');
  const [embeddedFiles, setEmbeddedFiles] = useState([]);
  const [indexingResult, setIndexingResult] = useState(null);
  const [collections, setCollections] = useState([]);
  const [selectedCollection, setSelectedCollection] = useState('');
  const [collectionDetails, setCollectionDetails] = useState(null);
  const [providers, setProviders] = useState([]);
  //const [selectedProvider, setSelectedProvider] = useState('milvus');
  const [selectedProvider, setSelectedProvider] = useState('chroma');


  // 数据库和索引模式的配置
  const dbConfigs = {
    pinecone: {
      modes: ['standard', 'hybrid']
    },
    milvus: {
      modes: ['flat', 'ivf_flat', 'ivf_sq8', 'hnsw']
    },
    qdrant: {
      modes: ['hnsw', 'custom']
    },
    weaviate: {
      modes: ['hnsw', 'flat']
    },
    chroma: {
      modes: ['hnsw', 'standard']
    },
    faiss: {
      modes: ['flat', 'ivf', 'hnsw']
    }
  };

  useEffect(() => {
    fetchEmbeddedFiles();
    fetchCollections();
  }, []);

  useEffect(() => {
    // 当数据库改变时，重置索引模式为该数据库的第一个可用模式
    setIndexMode(dbConfigs[vectorDb].modes[0]);
  }, [vectorDb]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // 获取providers列表
        const providersResponse = await fetch(`${apiBaseUrl}/providers`);
        const providersData = await providersResponse.json();
        setProviders(providersData.providers);

        // 获取collections列表
        const collectionsResponse = await fetch(`${apiBaseUrl}/collections?provider=${selectedProvider}`);
        const collectionsData = await collectionsResponse.json();
        setCollections(collectionsData.collections);
      } catch (error) {
        console.error('Error fetching data:', error);
      }
    };

    fetchData();
  }, [selectedProvider]);

  const fetchEmbeddedFiles = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/list-embedded`);
      const data = await response.json();
      if (data.documents) {
        setEmbeddedFiles(data.documents.map(doc => ({
          ...doc,
          id: doc.name,
          displayName: doc.name
        })));
      }
    } catch (error) {
      console.error('Error fetching embedded files:', error);
      setStatus('Error loading embedding files');
    }
  };

  const fetchCollections = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/collections}`);
      const data = await response.json();
      setCollections(data.collections || []);
    } catch (error) {
      console.error('Error fetching collections:', error);
    }
  };

  const handleIndex = async () => {
    if (!embeddingFile) {
      setStatus('Please select an embedding file');
      return;
    }

    setStatus('Indexing...');
    try {
      const response = await fetch(`${apiBaseUrl}/index`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          fileId: embeddingFile,
          vectorDb,
          indexMode
        }),
      });
      
      const data = await response.json();
      setIndexingResult(data);
      setStatus('Indexing completed successfully');
    } catch (error) {
      console.error('Error indexing:', error);
      setStatus('Error during indexing: ' + error.message);
    }
  };

  const handleDisplay = async (collectionName) => {
    if (!collectionName) return;
    
    try {
      const response = await fetch(`${apiBaseUrl}/collections/${selectedProvider}/${collectionName}`);
      const data = await response.json();
      console.log("after await")
      
      // 只包含有实际值的属性
      const result = {
        database: selectedProvider,
        collection_name: data.name,
        total_vectors: data.num_entities,
        index_size: data.num_entities
      };

      // 只在有实际值时添加可选属性
      //const indexType="hnsw"

     // const indexType = data.schema?.fields?.find(f => f.name === 'vector')?.index_params?.index_type;
     // if (indexType) {
     //   result.index_mode = indexType;
     // }

      if (data.processing_time) {
        result.processing_time = data.processing_time;
      }

      setIndexingResult(result);
    } catch (error) {
      console.error('Error displaying collection:', error);
    }
  };

  const handleDelete = async (collectionName) => {
    if (!collectionName) return;
    
    if (window.confirm(`Are you sure you want to delete collection "${collectionName}"?`)) {
      try {
        await fetch(`${apiBaseUrl}/collections/${selectedProvider}/${collectionName}`, {
          method: 'DELETE',
        });
        setSelectedCollection('');
        // 重新获取collections列表
        const response = await fetch(`${apiBaseUrl}/collections?provider=${selectedProvider}`);
        const data = await response.json();
        setCollections(data.collections);
      } catch (error) {
        console.error('Error deleting collection:', error);
      }
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-blue-500 text-3xl font-bold text-center mb-6"> 检索增强生成工具 </h1>
      <hr />
      <h2 className="text-2xl font-bold mb-6">向量库索引</h2>
      
      <div className="grid grid-cols-12 gap-6">
        {/* Left Panel - Controls */}
        <div className="col-span-3">
          <div className="p-4 border rounded-lg bg-white shadow-sm space-y-4">
            {/* Embedding File Selection */}
            <div>
              <label className="block text-sm font-medium mb-1">需要索引的文件</label>
              <select
                value={embeddingFile}
                onChange={(e) => setEmbeddingFile(e.target.value)}
                className="block w-full p-2 border rounded"
              >
                <option value="">Choose a file...</option>
                {embeddedFiles.map(file => (
                  <option key={file.name} value={file.name}>
                    {file.displayName}
                  </option>
                ))}
              </select>
            </div>

            {/* Vector Database Selection */}
            <div>
              <label className="block text-sm font-medium mb-1">向量库</label>
              <select
                value={selectedProvider}
                onChange={(e) => setSelectedProvider(e.target.value)}
                className="block w-full p-2 border rounded"
              >
                {providers.map(provider => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Index Mode Selection */}
            <div>
              <label className="block text-sm font-medium mb-1">索引模式</label>
              <select
                value={indexMode}
                onChange={(e) => setIndexMode(e.target.value)}
                className="block w-full p-2 border rounded"
              >
                {dbConfigs[vectorDb].modes.map(mode => (
                  <option key={mode} value={mode}>
                    {mode.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>

            {/* Action Buttons and Collection Management */}
            <div className="space-y-2">
              {/* Index Data Button */}
              <button 
                onClick={handleIndex}
                className="w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-blue-300"
                disabled={!embeddingFile}
              >
                索引数据
              </button>

              {/* Collection Selection */}
              <div>
                <label className="block text-sm font-medium mb-1">索引集合</label>
                <select
                  value={selectedCollection}
                  onChange={(e) => setSelectedCollection(e.target.value)}
                  className="block w-full p-2 border rounded"
                >
                  <option value="">Choose a collection...</option>
                  {collections.map(coll => (
                    <option key={coll.id} value={coll.id}>
                      {coll.name} ({coll.count} documents)
                    </option>
                  ))}
                </select>
              </div>

              {/* Display Collection Button */}
              <button
                onClick={() => handleDisplay(selectedCollection)}
                disabled={!selectedCollection}
                className="w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-blue-300"
              >
                显示集合
              </button>

              {/* Delete Collection Button */}
              <button
                onClick={() => handleDelete(selectedCollection)}
                disabled={!selectedCollection}
                className="w-full px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 disabled:bg-red-300"
              >
                删除集合
              </button>
            </div>

            {status && (
              <div className="mt-4 p-3 rounded border bg-gray-50">
                <p className="text-sm">{status}</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Panel - Results */}
        <div className="col-span-9 border rounded-lg bg-white shadow-sm">
          {indexingResult ? (
            <div className="p-4">
              <h3 className="text-xl font-semibold mb-4">索引结果</h3>
              <div className="space-y-3">
                <div className="p-3 border rounded bg-gray-50">
                  <div className="text-sm text-gray-600">
                    <p>Database: {indexingResult.database}</p>
                    {indexingResult.index_mode && (
                      <p>Index Mode: {indexingResult.index_mode}</p>
                    )}
                    <p>Total Vectors: {indexingResult.total_vectors}</p>
                    <p>Index Size: {indexingResult.index_size}</p>
                    {indexingResult.processing_time && (
                      <p>Processing Time: {indexingResult.processing_time}s</p>
                    )}
                    <p>Collection Name: {indexingResult.collection_name}</p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <RandomImage message="Indexing results will appear here" />
          )}
        </div>
      </div>
    </div>
  );
};

export default Indexing;