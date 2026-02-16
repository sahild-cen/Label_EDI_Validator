import { useState, useEffect } from 'react';
import { Upload, Trash2, CheckCircle } from 'lucide-react';
import { api, Carrier } from '../services/api';

export default function CarrierSetup() {
  const [carriers, setCarriers] = useState<Carrier[]>([]);
  const [carrierName, setCarrierName] = useState('');
  const [labelSpec, setLabelSpec] = useState<File | null>(null);
  const [ediSpec, setEdiSpec] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

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

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!carrierName.trim()) {
      setMessage({ type: 'error', text: 'Please enter a carrier name' });
      return;
    }

    if (!labelSpec && !ediSpec) {
      setMessage({ type: 'error', text: 'Please upload at least one specification file' });
      return;
    }

    setUploading(true);
    setMessage(null);

    try {
      const formData = new FormData();
      formData.append('carrier_name', carrierName);
      if (labelSpec) formData.append('label_spec', labelSpec);
      if (ediSpec) formData.append('edi_spec', ediSpec);

      const response = await api.uploadCarrierSpec(formData);

      if (response.success) {
        setMessage({ type: 'success', text: `Carrier '${carrierName}' uploaded successfully!` });
        setCarrierName('');
        setLabelSpec(null);
        setEdiSpec(null);
        loadCarriers();
      } else {
        setMessage({ type: 'error', text: 'Upload failed. Please try again.' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Upload failed. Please check your connection.' });
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (carrierId: string, carrierName: string) => {
    if (!confirm(`Delete carrier '${carrierName}'?`)) return;

    try {
      await api.deleteCarrier(carrierId);
      setMessage({ type: 'success', text: `Carrier '${carrierName}' deleted successfully` });
      loadCarriers();
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to delete carrier' });
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Carrier Setup</h1>
          <p className="text-gray-600">Upload carrier specifications to create validation rule templates</p>
        </div>

        {message && (
          <div className={`mb-6 p-4 rounded-lg flex items-center gap-2 ${
            message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
          }`}>
            {message.type === 'success' && <CheckCircle className="w-5 h-5" />}
            <span>{message.text}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Upload New Carrier</h2>

            <form onSubmit={handleUpload} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Carrier Name
                </label>
                <input
                  type="text"
                  value={carrierName}
                  onChange={(e) => setCarrierName(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="e.g., DHL, UPS, FedEx"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Label Specification (PDF)
                </label>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 hover:border-blue-500 transition-colors">
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={(e) => setLabelSpec(e.target.files?.[0] || null)}
                    className="w-full"
                  />
                  {labelSpec && (
                    <p className="mt-2 text-sm text-green-600 flex items-center gap-2">
                      <CheckCircle className="w-4 h-4" />
                      {labelSpec.name}
                    </p>
                  )}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  EDI Specification (PDF)
                </label>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 hover:border-blue-500 transition-colors">
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={(e) => setEdiSpec(e.target.files?.[0] || null)}
                    className="w-full"
                  />
                  {ediSpec && (
                    <p className="mt-2 text-sm text-green-600 flex items-center gap-2">
                      <CheckCircle className="w-4 h-4" />
                      {ediSpec.name}
                    </p>
                  )}
                </div>
              </div>

              <button
                type="submit"
                disabled={uploading}
                className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                <Upload className="w-5 h-5" />
                {uploading ? 'Uploading...' : 'Upload Carrier Specs'}
              </button>
            </form>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Configured Carriers</h2>

            {carriers.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <p>No carriers configured yet</p>
                <p className="text-sm mt-2">Upload a carrier specification to get started</p>
              </div>
            ) : (
              <div className="space-y-3">
                {carriers.map((carrier) => (
                <div
                  key={carrier._id}
                  className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:border-blue-500 transition-colors"
                >
                  <div>
                    <h3 className="font-medium text-gray-900">{carrier.carrier}</h3>
                  </div>

                  <button
                    onClick={() => handleDelete(carrier._id, carrier.carrier)}
                    className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                </div>
              ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
