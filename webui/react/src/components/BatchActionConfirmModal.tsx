import React from 'react';

import { UNMANAGED_EXPERIMENT_ANNOTATION_MESSAGE } from 'constant';
import { ExperimentAction } from 'types';
import handleError from 'utils/error';

import { Modal } from './kit/Modal';

interface Props {
  batchAction: ExperimentAction;
  itemName?: string;
  isUnmanagedIncluded?: boolean;
  onConfirm: () => Promise<void>;
  onClose?: () => void;
}

export const CONFIRM_BUTTON_LABEL = 'Confirm';

const DANGEROUS_BATCH_ACTIONS: ExperimentAction[] = [
  ExperimentAction.Cancel,
  ExperimentAction.Delete,
  ExperimentAction.Kill,
];

const BatchActionConfirmModalComponent: React.FC<Props> = ({
  batchAction,
  itemName = 'experiment',
  isUnmanagedIncluded,
  onConfirm,
  onClose,
}: Props) => {
  const danger = DANGEROUS_BATCH_ACTIONS.includes(batchAction);
  const submit = {
    handleError,
    handler: onConfirm,
    text: batchAction === ExperimentAction.Cancel ? CONFIRM_BUTTON_LABEL : batchAction,
  };

  return (
    <Modal
      cancel
      danger={danger}
      icon="info"
      size="small"
      submit={submit}
      title={`Confirm Batch ${batchAction}`}
      onClose={onClose}>
      <div>
        Are you sure you want to <b>{batchAction.toLocaleLowerCase()}</b> all selected {itemName}s?
      </div>
      {isUnmanagedIncluded && (
        <div>
          <small>{UNMANAGED_EXPERIMENT_ANNOTATION_MESSAGE}</small>
        </div>
      )}
    </Modal>
  );
};

export default BatchActionConfirmModalComponent;
