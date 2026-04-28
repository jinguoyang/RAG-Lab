import { RouterProvider } from 'react-router';
import { router } from './routes';
import { ConfirmDialogProvider } from './components/rag/ConfirmDialog';

export default function App() {
  return (
    <ConfirmDialogProvider>
      <RouterProvider router={router} />
    </ConfirmDialogProvider>
  );
}
