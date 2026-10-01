Payment Split
=============

This module allows to specify the amount paid on each invoice in a multi-invoice payment.

Usage
=====

- Create and validate more than one invoice for the same partner.

- Select the invoices in the tree view and use the Register Payment action.

  .. image:: account_payment_split/static/src/img/tree_view.png
    :width: 400pt
    :alt: Tree view

- Select currency, journal and amount.

  .. image:: account_payment_split/static/src/img/register_payment.png
    :width: 400pt
    :alt: Register payment

- You can change the rate using the custom rate for all lines ( or the rate field for a specific line - This feature is not supported in this version).

  .. image:: account_payment_split/static/src/img/custom_rate.png
    :width: 400pt
    :alt: Custom Rate

- Check the payment lines for each invoice.

  * Blue lines mean a correct partial payment

    .. image:: account_payment_split/static/src/img/with_partial.png
      :width: 400pt
      :alt: With partial payment

  * Normal lines mean a correct total payment

    .. image:: account_payment_split/static/src/img/total_paid.png
      :width: 400pt
      :alt: Total payment

  * Red lines mean the payment amount is bigger than the due amount.

    .. image:: account_payment_split/static/src/img/red_line.png
      :width: 400pt
      :alt: Red line

- Change the payment amount or the payment currency amount if it's necessary.

- Validate the payment.

- Important Notice:
  Be aware that when running for the first time the wizard it will try to pay in full at the invoices.
  By doing so, when multi-currency invoices is involved, a special case is performed.
  We try the most to pay in full the invoices in the invoice currency too, to avoid leaving small cents to be paid later.
  For example:
  - Be your company currency MXN.
  - Be the invoice your are going to pay in MXN too: MXN 627.68
  - Be your payment currency in USD. That is, you have selected a Journal in USD.
  - Set a custom_rate of 23.00 MXN / USD
  - Check for the computed rate in the line: 23.000366434591

  Why is this done this way? Get your calculator on hand.
  Make the division: 627.68 / 23.00 => 27.290434782608696 which you would round to two digits, yielding 27.29.
  Now this amount in USD must be booked in MXN (company currency at the rate of
  your selection with two digits for rounding): 627.67.
  As you can see the conversion yields almost the same value that is to be paid
  for your invoice. But this will leave a small amount to be reconciled: MXN 0.01.
  Thus we, by design, have decide to round up to the full amount of the invoice.
  This only happens when half of a cent of the foreign currency converted to
  local currency is greater than the reamining value to be paid in full. That
  is, 0.01 / 2 * 23.00 => MXN 0.12 is greater than MXN 0.01. Then if we do this
  for greater or lesser values you would realize about this:
  - 27.28 * 23 = 627.44
  - 27.29 * 23 = 627.67 --> This is our value which is the closes one to 627.68
  - 27.30 * 23 = 627.90

  This only applies for the edge case when the invoice is intended to be paid in full.
