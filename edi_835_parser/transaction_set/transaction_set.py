from typing import List, Iterator, Optional
from collections import namedtuple

import pandas as pd

from edi_835_parser.loops.claim import Claim as ClaimLoop
from edi_835_parser.loops.service import Service as ServiceLoop
from edi_835_parser.loops.organization import Organization as OrganizationLoop
from edi_835_parser.segments.utilities import find_identifier
from edi_835_parser.segments.interchange import Interchange as InterchangeSegment
from edi_835_parser.segments.financial_information import FinancialInformation as FinancialInformationSegment


BuildAttributeResponse = namedtuple('BuildAttributeResponse', 'key value segment segments')


class TransactionSet:

	def __init__(
			self,
			interchange: InterchangeSegment,
			financial_information: FinancialInformationSegment,
			claims: List[ClaimLoop],
			organizations: List[OrganizationLoop]
	):
		self.interchange = interchange
		self.financial_information = financial_information
		self.claims = claims
		self.organizations = organizations

	def __repr__(self):
		return '\n'.join(str(item) for item in self.__dict__.items())

	@property
	def payer(self) -> OrganizationLoop:
		payer = [o for o in self.organizations if o.organization.type == 'payer']
		# hack multiple payers... choose the last one.
		assert len(payer) == 1
		return payer[0]

	@property
	def payee(self) -> OrganizationLoop:
		payee = [o for o in self.organizations if o.organization.type == 'payee']
		assert len(payee) == 1
		return payee[0]

	def to_dataframe(self) -> pd.DataFrame:
		"""flatten the remittance advice by service to a pandas DataFrame"""
		data = []
		for claim in self.claims:
			for service in claim.services:

				datum = TransactionSet.serialize_service(
					self.financial_information,
					# self.payer, -- replace with claim.myPayer
					claim.myPayer, # this is the payer that's attached to the claim (from class method build of this object)
					claim,
					service
				)
				for index, adjustment in enumerate(service.adjustments):
					datum[f'adj_{index}_group'] = adjustment.group_code.code
					datum[f'adj_{index}_code'] = adjustment.reason_code.code
					datum[f'adj_{index}_amount'] = adjustment.amount

				for index, reference in enumerate(service.references):
					datum[f'ref_{index}_qual'] = reference.qualifier.code
					datum[f'ref_{index}_desc'] = reference.qualifier.description
					datum[f'ref_{index}_value'] = reference.value

				for index, remark in enumerate(service.remarks):
					datum[f'rem_{index}_qual'] = remark.qualifier.code
					datum[f'rem_{index}_code'] = remark.code.code

				data.append(datum)

		data = pd.DataFrame(data)

		return pd.DataFrame(data)

	@staticmethod
	def serialize_service(
			financial_information: FinancialInformationSegment,
			payer: OrganizationLoop,
			claim: ClaimLoop,
			service: ServiceLoop,
	) -> dict:
		# if the service doesn't have a start date assume the service and claim dates match
		start_date = None
		if service.service_period_start:
			start_date = service.service_period_start.date
		elif claim.claim_statement_period_start:
			start_date = claim.claim_statement_period_start.date

		# if the service doesn't have an end date assume the service and claim dates match
		end_date = None
		if service.service_period_end:
			end_date = service.service_period_end.date
		elif claim.claim_statement_period_end:
			end_date = claim.claim_statement_period_end.date

		datum = {
			'marker': claim.claim.marker,
			'patient': claim.patient.name,
			'patient_hic': claim.patient.identification_code,
			'code': service.service.code,
			'modifier': service.service.modifier,
			'qualifier': service.service.qualifier,
			'allowed_units': service.service.allowed_units,
			'billed_units': service.service.billed_units,
			'transaction_date': financial_information.transaction_date,
			'transaction_date_str': financial_information.transaction_date.strftime("%Y/%m/%d"),
			'transaction_method': financial_information._payment_method,
			'charge_amount': service.service.charge_amount,
			'allowed_amount': service.allowed_amount,
			'paid_amount': service.service.paid_amount,
			'payer': payer.organization.name,
			'start_date': start_date,
			'start_date_str': start_date.strftime("%Y/%m/%d"),
			'end_date': end_date,
			'end_date_str': end_date.strftime("%Y/%m/%d"),
			'rendering_provider': claim.rendering_provider.name if claim.rendering_provider else None,
			'rendering_provider_id': claim.rendering_provider.identification_code if claim.rendering_provider else None,
		}

		return datum

	@classmethod
	def build(cls, file_path: str, strInput: bool=False) -> 'TransactionSet':
		# if strInput == true, parse content of path instead of reading files from path to parse.
		interchange = None
		financial_information = None
		claims = []
		organizations = []

		# --- strInput hack starts
		if (strInput):
			file = file_path
		else:
			with open(file_path) as f:
				file = f.read()
		# --- strInput hack ends

		segments = file.split('~')
		segments = [segment.strip() for segment in segments]

		segments = iter(segments)
		segment = None

		_payer = None # attach newest payer to claim

		while True:
			response = cls.build_attribute(segment, segments)
			segment = response.segment
			segments = response.segments

			# no more segments to parse
			if response.segments is None:
				break

			if response.key == 'interchange':
				interchange = response.value

			if response.key == 'financial information':
				financial_information = response.value

			if response.key == 'organization':
				if response.value.organization.type == 'payer':
					_payer = response.value # save most recent payer encountered
				organizations.append(response.value)

			if response.key == 'claim':
				response.value.myPayer = _payer # attach payer to claim
				claims.append(response.value)

		return TransactionSet(interchange, financial_information, claims, organizations)

	@classmethod
	def build_attribute(cls, segment: Optional[str], segments: Iterator[str]) -> BuildAttributeResponse:
		if segment is None:
			try:
				segment = segments.__next__()
			except StopIteration:
				return BuildAttributeResponse(None, None, None, None)

		identifier = find_identifier(segment)

		if identifier == InterchangeSegment.identification:
			interchange = InterchangeSegment(segment)
			return BuildAttributeResponse('interchange', interchange, None, segments)

		if identifier == FinancialInformationSegment.identification:
			financial_information = FinancialInformationSegment(segment)
			return BuildAttributeResponse('financial information', financial_information, None, segments)

		if identifier == OrganizationLoop.initiating_identifier:
			organization, segments, segment = OrganizationLoop.build(segment, segments)
			return BuildAttributeResponse('organization', organization, segment, segments)

		elif identifier == ClaimLoop.initiating_identifier:
			claim, segments, segment = ClaimLoop.build(segment, segments)
			return BuildAttributeResponse('claim', claim, segment, segments)

		else:
			return BuildAttributeResponse(None, None, None, segments)


if __name__ == '__main__':
	pass