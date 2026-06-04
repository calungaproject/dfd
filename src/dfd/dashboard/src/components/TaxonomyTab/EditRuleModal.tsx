import { useState, useEffect } from 'react';
import {
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  Button,
  Form,
  FormGroup,
  TextInput,
  TextArea,
  FormSelect,
  FormSelectOption,
} from '@patternfly/react-core';
import type { TaxonomyRule } from '../../api/types';

interface EditRuleModalProps {
  rule: TaxonomyRule;
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: Partial<TaxonomyRule>) => void;
  isSaving: boolean;
}

const CATEGORIES = ['build', 'infra', 'unknown'];

export default function EditRuleModal({
  rule,
  isOpen,
  onClose,
  onSave,
  isSaving,
}: EditRuleModalProps) {
  const [rootCause, setRootCause] = useState(rule.root_cause);
  const [category, setCategory] = useState(rule.category);
  const [errorSignature, setErrorSignature] = useState(rule.error_signature);
  const [priorityRule, setPriorityRule] = useState(rule.priority_rule ?? '');
  const [recipe, setRecipe] = useState(rule.investigation_recipe ?? '');

  useEffect(() => {
    setRootCause(rule.root_cause);
    setCategory(rule.category);
    setErrorSignature(rule.error_signature);
    setPriorityRule(rule.priority_rule ?? '');
    setRecipe(rule.investigation_recipe ?? '');
  }, [rule]);

  function handleSave() {
    const updates: Partial<TaxonomyRule> = {};
    if (rootCause !== rule.root_cause) updates.root_cause = rootCause;
    if (category !== rule.category) updates.category = category;
    if (errorSignature !== rule.error_signature) updates.error_signature = errorSignature;
    if (priorityRule !== (rule.priority_rule ?? '')) updates.priority_rule = priorityRule;
    if (recipe !== (rule.investigation_recipe ?? '')) updates.investigation_recipe = recipe;

    if (Object.keys(updates).length === 0) {
      onClose();
      return;
    }
    onSave(updates);
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      variant="large"
      aria-label="Edit taxonomy rule"
    >
      <ModalHeader title={`Edit rule #${rule.id}: ${rule.root_cause}`} />
      <ModalBody>
        <Form>
          <FormGroup label="Root Cause" isRequired fieldId="edit-root-cause">
            <TextInput
              id="edit-root-cause"
              value={rootCause}
              onChange={(_e, val) => setRootCause(val)}
            />
          </FormGroup>
          <FormGroup label="Category" isRequired fieldId="edit-category">
            <FormSelect
              id="edit-category"
              value={category}
              onChange={(_e, val) => setCategory(val)}
            >
              {CATEGORIES.map((c) => (
                <FormSelectOption key={c} value={c} label={c} />
              ))}
            </FormSelect>
          </FormGroup>
          <FormGroup label="Error Signature" isRequired fieldId="edit-error-sig">
            <TextArea
              id="edit-error-sig"
              value={errorSignature}
              onChange={(_e, val) => setErrorSignature(val)}
              rows={3}
            />
          </FormGroup>
          <FormGroup label="Priority Rule" fieldId="edit-priority-rule">
            <TextArea
              id="edit-priority-rule"
              value={priorityRule}
              onChange={(_e, val) => setPriorityRule(val)}
              rows={3}
            />
          </FormGroup>
          <FormGroup label="Investigation Recipe" fieldId="edit-recipe">
            <TextArea
              id="edit-recipe"
              value={recipe}
              onChange={(_e, val) => setRecipe(val)}
              rows={8}
            />
          </FormGroup>
        </Form>
      </ModalBody>
      <ModalFooter>
        <Button
          variant="primary"
          onClick={handleSave}
          isLoading={isSaving}
          isDisabled={isSaving}
        >
          Save
        </Button>
        <Button variant="link" onClick={onClose} isDisabled={isSaving}>
          Cancel
        </Button>
      </ModalFooter>
    </Modal>
  );
}
