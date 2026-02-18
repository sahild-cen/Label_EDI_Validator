import { useState, useEffect } from 'react';
import { FileCheck, AlertCircle, Copy, CheckCircle } from 'lucide-react';
import { api, Carrier, ValidationResult } from '../services/api';

export default function ValidationDashboard() {
  const [carriers, setCarriers] = useState<Carrier[]>([]);
  const [selectedCarrier, setSelectedCarrier] = useState('');
  const [labelFile, setLabelFile] = useState<File | null>(null);
  const [ediFile, setEdiFile] = useState<File | null>(null);
  const [isZpl, setIsZpl] = useState(false);
  const [validating, setValidating] = useState(false);
  const [labelResult, setLabelResult] = useState<ValidationResult | null>(null);
  const [ediResult, setEdiResult] = useState<ValidationResult | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    loadCarriers();
  }, []);

  const loadCarriers = async () => {
    try {
      const response = await api.listCarriers();
      if (response.success) {
        setCarriers(response.carriers);
      }
    } catch (error) {
      console.error('Failed to load carriers:', error);
    }
  };

  const handleValidateLabel = async () => {
    if (!selectedCarrier || !labelFile) return;

    setValidating(true);
    setLabelResult(null);

    try {
      const response = await api.validateLabel(selectedCarrier, labelFile, isZpl);
      if (response.success) {
        setLabelResult(response.validation);   // ✅ FIXED
      }
    } catch (error) {
      console.error('Validation failed:', error);
    } finally {
      setValidating(false);
    }
  };


  const handleValidateEDI = async () => {
    if (!selectedCarrier || !ediFile) return;

    setValidating(true);
    setEdiResult(null);

    try {
      const response = await api.validateEDI(selectedCarrier, ediFile);
      if (response.success) {
        setEdiResult(response.validation);
      }
    } catch (error) {
      console.error('Validation failed:', error);
    } finally {
      setValidating(false);
    }
  };

  const copyToClipboard = (text: string, type: string) => {
    navigator.clipboard.writeText(text);
    setCopied(type);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Validation Dashboard</h1>
          <p className="text-gray-600">Validate shipping labels and EDI files against carrier specifications</p>
        </div>

        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Select Carrier</h2>
          <select
            value={selectedCarrier}
            onChange={(e) => setSelectedCarrier(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="">Choose a carrier...</option>
            {carriers.map((carrier) => (
              <option key={carrier._id} value={carrier._id}>
                {carrier.carrier}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <FileCheck className="w-5 h-5" />
              Label Validation
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Upload Label File
                </label>
                <input
                  type="file"
                  accept=".zpl,.png,.jpg,.jpeg,.pdf"
                  onChange={(e) => setLabelFile(e.target.files?.[0] || null)}
                  className="w-full"
                />
              </div>

              {/* <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="isZpl"
                  checked={isZpl}
                  onChange={(e) => setIsZpl(e.target.checked)}
                  className="w-4 h-4"
                />
                <label htmlFor="isZpl" className="text-sm text-gray-700">
                  This is a ZPL file
                </label>
              </div> */}

              <button
                onClick={handleValidateLabel}
                disabled={!selectedCarrier || !labelFile || validating}
                className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                {validating ? 'Validating...' : 'Validate Label'}
              </button>

              {labelResult && (
                <div className="mt-6 space-y-4">
                  <div className={`p-4 rounded-lg ${
                    labelResult.status === 'PASS' ? 'bg-green-50' : 'bg-red-50'
                  }`}>
                    <div className="flex items-center gap-2 mb-2">
                      {labelResult.status === 'PASS' ? (
                        <CheckCircle className="w-5 h-5 text-green-600" />
                      ) : (
                        <AlertCircle className="w-5 h-5 text-red-600" />
                      )}
                      <span className={`font-semibold ${
                        labelResult.status === 'PASS' ? 'text-green-800' : 'text-red-800'
                      }`}>
                        {labelResult.status}
                      </span>
                    </div>
                    <p className="text-sm">
                      {labelResult.status === 'PASS'
                        ? 'Label is valid and ready to use.'
                        : `${labelResult.errors.length} issue(s) found. Please review below.`}
                    </p>
                  </div>

                  {labelResult.errors && labelResult.errors.length > 0 && (
                    <div>
                      <h3 className="font-medium mb-2">Errors Found:</h3>
                      <div className="space-y-2">
                        {labelResult.errors.map((error, idx) => (
                          <div key={idx} className="bg-red-50 p-3 rounded border border-red-200">
                            <p className="font-medium text-red-900">{error.field}</p>
                            <p className="text-sm text-red-700">{error.description}</p>
                            <p className="text-xs text-red-600 mt-1">
                              Expected: {error.expected} | Actual: {error.actual}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {labelResult.corrected_label_script && (
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="font-medium">Corrected Label Script</h3>
                        <button
                          onClick={() => copyToClipboard(labelResult.corrected_label_script!, 'label')}
                          className="flex items-center gap-2 px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded text-sm"
                        >
                          {copied === 'label' ? (
                            <>
                              <CheckCircle className="w-4 h-4" />
                              Copied!
                            </>
                          ) : (
                            <>
                              <Copy className="w-4 h-4" />
                              Copy
                            </>
                          )}
                        </button>
                      </div>
                      <pre className="bg-gray-100 p-4 rounded text-sm overflow-x-auto">
                        {labelResult.corrected_label_script}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <FileCheck className="w-5 h-5" />
              EDI Validation
            </h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Upload EDI File
                </label>
                <input
                  type="file"
                  accept=".edi,.txt,.json,.xml"
                  onChange={(e) => setEdiFile(e.target.files?.[0] || null)}
                  className="w-full"
                />
              </div>

              <button
                onClick={handleValidateEDI}
                disabled={!selectedCarrier || !ediFile || validating}
                className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                {validating ? 'Validating...' : 'Validate EDI'}
              </button>

              {ediResult && (
                <div className="mt-6 space-y-4">
                  <div className={`p-4 rounded-lg ${
                    ediResult.status === 'PASS' ? 'bg-green-50' : 'bg-red-50'
                  }`}>
                    <div className="flex items-center gap-2 mb-2">
                      {ediResult.status === 'PASS' ? (
                        <CheckCircle className="w-5 h-5 text-green-600" />
                      ) : (
                        <AlertCircle className="w-5 h-5 text-red-600" />
                      )}
                      <span className={`font-semibold ${
                        ediResult.status === 'PASS' ? 'text-green-800' : 'text-red-800'
                      }`}>
                        {ediResult.status}
                      </span>
                    </div>
                    <p className="text-sm">
                      Compliance Score: {(ediResult.compliance_score * 100).toFixed(1)}%
                    </p>
                  </div>

                  {ediResult.errors && ediResult.errors.length > 0 && (
                    <div>
                      <h3 className="font-medium mb-2">Errors Found:</h3>
                      <div className="space-y-2">
                        {ediResult.errors.map((error, idx) => (
                          <div key={idx} className="bg-red-50 p-3 rounded border border-red-200">
                            <p className="font-medium text-red-900">{error.field}</p>
                            <p className="text-sm text-red-700">{error.description}</p>
                            <p className="text-xs text-red-600 mt-1">
                              Expected: {error.expected} | Actual: {error.actual}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {ediResult.corrected_edi_script && (
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="font-medium">Corrected EDI Script</h3>
                        <button
                          onClick={() => copyToClipboard(ediResult.corrected_edi_script!, 'edi')}
                          className="flex items-center gap-2 px-3 py-1 bg-gray-100 hover:bg-gray-200 rounded text-sm"
                        >
                          {copied === 'edi' ? (
                            <>
                              <CheckCircle className="w-4 h-4" />
                              Copied!
                            </>
                          ) : (
                            <>
                              <Copy className="w-4 h-4" />
                              Copy
                            </>
                          )}
                        </button>
                      </div>
                      <pre className="bg-gray-100 p-4 rounded text-sm overflow-x-auto">
                        {ediResult.corrected_edi_script}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
