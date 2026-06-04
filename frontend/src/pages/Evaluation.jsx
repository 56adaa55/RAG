import { useEffect, useMemo, useState } from 'react';
import RandomImage from '../components/RandomImage';
import { apiBaseUrl } from '../config/config';

const Evaluation = () => {
  const [file, setFile] = useState(null);
  const [collection, setCollection] = useState('');
  const [collections, setCollections] = useState([]);
  const [providers, setProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState('chroma');
  const [topK, setTopK] = useState(5);
  const [threshold, setThreshold] = useState(0.7);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [status, setStatus] = useState('');
  const [evaluationResult, setEvaluationResult] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const providersResponse = await fetch(`${apiBaseUrl}/providers`);
        if (!providersResponse.ok) {
          throw new Error(`HTTP error! status: ${providersResponse.status}`);
        }
        const providersData = await providersResponse.json();
        setProviders(providersData.providers || []);

        const collectionsResponse = await fetch(`${apiBaseUrl}/collections?provider=${selectedProvider}`);
        if (!collectionsResponse.ok) {
          throw new Error(`HTTP error! status: ${collectionsResponse.status}`);
        }
        const collectionsData = await collectionsResponse.json();
        setCollections(collectionsData.collections || []);
        setCollection('');
      } catch (error) {
        console.error('Error fetching evaluation data:', error);
        setStatus(`加载集合失败: ${error.message}`);
      }
    };

    fetchData();
  }, [selectedProvider]);

  const resultRows = useMemo(() => {
    if (!evaluationResult?.results) return [];
    return evaluationResult.results;
  }, [evaluationResult]);

  const formatPercent = (value) => {
    if (typeof value !== 'number') return 'N/A';
    return `${(value * 100).toFixed(1)}%`;
  };

  const handleEvaluate = async () => {
    if (!file || !collection) {
      setStatus('请选择评估文件和索引集合');
      return;
    }

    setIsEvaluating(true);
    setStatus('');
    setEvaluationResult(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('collection_id', collection);
      formData.append('top_k', topK);
      formData.append('threshold', threshold);

      const response = await fetch(`${apiBaseUrl}/evaluate`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setEvaluationResult(data);
      setStatus('评估完成，结果已保存');
    } catch (error) {
      console.error('Evaluation error:', error);
      setStatus(`评估失败: ${error.message}`);
    } finally {
      setIsEvaluating(false);
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-blue-500 text-3xl font-bold text-center mb-6"> 检索增强生成工具 </h1>
      <hr />
      <h2 className="text-2xl font-bold mb-6">检索效果评估</h2>

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-3 space-y-4">
          <div className="p-4 border rounded-lg bg-white shadow-sm">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">评估CSV文件</label>
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => setFile(e.target.files[0])}
                  className="block w-full border rounded px-3 py-2"
                />
                <div className="text-xs text-gray-500 mt-2">
                  需要包含 LABEL 列
                </div>
              </div>

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

              <div>
                <label className="block text-sm font-medium mb-1">集合</label>
                <select
                  value={collection}
                  onChange={(e) => setCollection(e.target.value)}
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

              <div>
                <label className="block text-sm font-medium mb-1">前K个检索结果</label>
                <input
                  type="number"
                  value={topK}
                  onChange={(e) => setTopK(parseInt(e.target.value, 10))}
                  min="1"
                  max="50"
                  className="block w-full p-2 border rounded"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  相似性阈值: {threshold}
                </label>
                <input
                  type="range"
                  value={threshold}
                  onChange={(e) => setThreshold(parseFloat(e.target.value))}
                  min="0"
                  max="1"
                  step="0.1"
                  className="block w-full"
                />
              </div>

              <button
                onClick={handleEvaluate}
                disabled={isEvaluating || !file || !collection}
                className="w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-blue-300"
              >
                {isEvaluating ? '评估过程中...' : '开始评估'}
              </button>
            </div>
          </div>

          {status && (
            <div className={`p-4 rounded-lg ${
              status.includes('失败') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
            }`}>
              {status}
            </div>
          )}
        </div>

        <div className="col-span-9 border rounded-lg bg-white shadow-sm">
          {evaluationResult ? (
            <div className="p-4">
              <h3 className="text-xl font-semibold mb-4">评估结果</h3>

              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="p-4 border rounded bg-gray-50">
                  <div className="text-sm text-gray-500">平均命中分</div>
                  <div className="text-2xl font-semibold text-blue-600">
                    {formatPercent(evaluationResult.average_scores?.score_hit)}
                  </div>
                </div>
                <div className="p-4 border rounded bg-gray-50">
                  <div className="text-sm text-gray-500">平均找回分</div>
                  <div className="text-2xl font-semibold text-green-600">
                    {formatPercent(evaluationResult.average_scores?.score_find)}
                  </div>
                </div>
                <div className="p-4 border rounded bg-gray-50">
                  <div className="text-sm text-gray-500">有效查询数</div>
                  <div className="text-2xl font-semibold text-gray-700">
                    {evaluationResult.total_queries}
                  </div>
                </div>
              </div>

              <div className="mb-4 p-3 border rounded bg-gray-100">
                <div className="text-sm text-gray-600">
                  <p>Collection: {evaluationResult.parameters?.collection_id}</p>
                  <p>Top K: {evaluationResult.parameters?.top_k}</p>
                  <p>Threshold: {evaluationResult.parameters?.threshold}</p>
                </div>
              </div>

              <div className="overflow-x-auto max-h-[calc(100vh-420px)]">
                <table className="min-w-full text-sm">
                  <thead className="sticky top-0 bg-gray-100">
                    <tr>
                      <th className="px-3 py-2 text-left border">Query</th>
                      <th className="px-3 py-2 text-left border">Expected Pages</th>
                      <th className="px-3 py-2 text-left border">Found Pages</th>
                      <th className="px-3 py-2 text-left border">Score Hit</th>
                      <th className="px-3 py-2 text-left border">Score Find</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resultRows.map((row, idx) => (
                      <tr key={`${row.query}-${idx}`} className="odd:bg-white even:bg-gray-50">
                        <td className="px-3 py-2 border align-top min-w-[280px]">
                          <div className="line-clamp-4">{row.query}</div>
                        </td>
                        <td className="px-3 py-2 border align-top">
                          {Array.isArray(row.expected_pages) ? row.expected_pages.join(', ') : row.expected_pages}
                        </td>
                        <td className="px-3 py-2 border align-top">
                          {Array.isArray(row.found_pages) ? row.found_pages.join(', ') : row.found_pages}
                        </td>
                        <td className="px-3 py-2 border align-top">
                          {formatPercent(row.score_hit)}
                        </td>
                        <td className="px-3 py-2 border align-top">
                          {formatPercent(row.score_find)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <RandomImage message="Evaluation results will appear here" />
          )}
        </div>
      </div>
    </div>
  );
};

export default Evaluation;
